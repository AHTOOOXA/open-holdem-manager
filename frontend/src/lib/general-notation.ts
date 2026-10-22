/**
 * Pure helpers for the General screen's stat popup and hands list
 * (docs/specs/H2N-COMPATIBLE-STATS.md section 6): number formats,
 * the action-token notation, card and position colours.
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

// ── Colours ────────────────────────────────────────────────────────

/** Four-colour deck: tile fill per suit, rank drawn in white. */
export const SUIT_COLORS: Record<string, string> = {
  s: '#525252',
  h: '#801000',
  c: '#018001',
  d: '#0059B3',
};

/** Token colour = position of the player who acted. */
export const POSITION_COLORS: Record<string, string> = {
  BTN: '#00FF00',
  CO: '#EEEE2A',
  MP: '#FF9E1C',
  EP: '#FF6B6B',
  UTG: '#FF6B6B',
  SB: '#00FFFF',
  BB: '#5CA0FF',
  STRADDLE: '#C98CFF',
};

export function positionColor(pos: string | null | undefined): string {
  if (!pos) return '#FFFFFF';
  return POSITION_COLORS[pos.toUpperCase()] ?? '#FFFFFF';
}

/** Colours of the popup and hands panes, sampled from the reference screenshot. */
export const POPUP_THEME = {
  /** Header, stat value and summary area of the popup; also the hands pane. */
  headerBg: '#212121',
  /** Tabs and tables area of the popup. */
  bodyBg: '#282828',
  titlePill: '#646464',
  label: '#8A8A8A',
  value: '#FFFFFF',
  tabInactive: '#737373',
  divider: '#383838',
  tableRule: '#1B1B1B',
  rowSelected: '#505038',
  rowHover: 'rgba(255,255,255,0.04)',
  segmentOutline: '#FAFF82',
  weakPill: 'rgba(33,33,33,0.75)',
  emptyBar: '#2A2A2A',
  emptyBarBorder: '#363636',
  handValue: '#FFFFFF80',
  plusN: '#8A8A8A',
} as const;

/** Header row of the popup tables (grey text over a dark rule). */
export const popupTableHeaderStyle = {
  color: POPUP_THEME.label,
  borderBottom: `1px solid ${POPUP_THEME.tableRule}`,
} as const;

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
