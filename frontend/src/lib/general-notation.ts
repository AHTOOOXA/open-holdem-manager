/**
 * Pure helpers for the General screen's stat popup and hands list
 * (docs/specs/H2N-COMPATIBLE-STATS.md section 6): number formats,
 * the action-token notation, card and position colour classes.
 *
 * No React here, so tests can run them from plain node
 * (frontend/tests/general-notation.test.ts).
 */

import { formatBbAmount } from './format/notation';

export {
  denoise,
  formatBbAmount,
  formatSignedBb,
  formatFrequency,
  formatWeak,
  formatRangeCount,
  barWidthPct,
  formatRatio,
  formatHandDate,
} from './format/notation';
export type { RatioLike, RatioDisplay } from './format/notation';

// ── Colours (token classes, src/index.css) ─────────────────────────

/** Card tile fill per suit (four-colour deck); the rank is drawn in white on it. */
const SUIT_CLASSES: Record<string, string> = {
  s: 'bg-suit-s',
  h: 'bg-suit-h',
  c: 'bg-suit-c',
  d: 'bg-suit-d',
};

export function suitClass(suit: string): string {
  return SUIT_CLASSES[suit] ?? SUIT_CLASSES.s;
}

/** Action-token colour = position of the player who acted; same palette as the General columns. */
const POSITION_CLASSES: Record<string, string> = {
  EP: 'text-pos-ep',
  UTG: 'text-pos-ep',
  MP: 'text-pos-mp',
  CO: 'text-pos-co',
  BTN: 'text-pos-btn',
  SB: 'text-pos-sb',
  BB: 'text-pos-bb',
};

export function positionClass(pos: string | null | undefined): string {
  if (!pos) return 'text-foreground';
  return POSITION_CLASSES[pos.toUpperCase()] ?? 'text-foreground';
}

/** Header row of the popup tables: column titles in the muted level over a rule. */
export const POPUP_TABLE_HEADER = 'border-b border-border text-muted-foreground';

// ── Cards ──────────────────────────────────────────────────────────

/** "Ah" → { rank: "A", suit: "h" }; "10d" → { rank: "T", suit: "d" }. */
export function cardParts(card: string): { rank: string; suit: string } | null {
  if (!card || card.length < 2) return null;
  let rank = card.slice(0, -1).toUpperCase();
  const suit = card.slice(-1).toLowerCase();
  if (rank === '10') rank = 'T';
  return { rank, suit };
}

// ── Action tokens ──────────────────────────────────────────────────

export interface TokenLike {
  t: string;
  amt_bb?: number | null;
  allin?: boolean;
}

/** "R3", "C2.6", "X", "R25'" (apostrophe = all-in). */
export function tokenText(a: TokenLike): string {
  const amt = a.amt_bb === null || a.amt_bb === undefined ? '' : formatBbAmount(a.amt_bb);
  return `${a.t}${amt}${a.allin ? "'" : ''}`;
}

/** Tokens shown per street before the grey "+N". */
export const MAX_TOKENS_PER_STREET = 3;

/** First `max` tokens, plus how many are hidden behind "+N" (0 when expanded). */
export function splitTokens<T>(tokens: readonly T[], expanded: boolean, max = MAX_TOKENS_PER_STREET): {
  shown: readonly T[];
  hidden: number;
} {
  if (expanded || tokens.length <= max) return { shown: tokens, hidden: 0 };
  return { shown: tokens.slice(0, max), hidden: tokens.length - max };
}

/** Street columns of a hand row, in order. */
export const HAND_STREETS = ['preflop', 'flop', 'turn', 'river'] as const;
export type HandStreet = (typeof HAND_STREETS)[number];

// ── Misc ───────────────────────────────────────────────────────────

/** The popup title: the stat's full name with every "->" drawn as an arrow. */
export function popupTitle(name: string): string {
  return name.replaceAll('->', '→');
}
