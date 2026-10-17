/**
 * Pure helpers for the General screen's stat popup and hands list
 * (docs/specs/H2N-COMPATIBLE-STATS.md section 6): number formats,
 * the action-token notation, card and position colours.
 *
 * No React here, so tests can run them from plain node
 * (frontend/tests/general-notation.test.ts).
 */

import {
  invariantString,
  resolveCellDisplay,
  roundHalfEven,
  roundHalfEvenInt,
  shortenCount,
} from './h2n-format';

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

// ── Numbers ────────────────────────────────────────────────────────

/**
 * Money and bb amounts arrive as doubles with float noise (4.199999999999999,
 * 6.000000000000001). Snap them to 9 decimals first so a value that is a
 * midpoint in exact arithmetic is rounded as one.
 */
export function denoise(x: number): number {
  return Math.round(x * 1e9) / 1e9;
}

/**
 * Amounts in big blinds (action tokens, street pots): below 5 one decimal
 * with a trailing ".0" dropped ("2.6", "4"), from 5 a whole number ("16").
 * Banker's rounding, like the rest of the screen.
 */
export function formatBbAmount(x: number): string {
  const v = denoise(x);
  if (Math.abs(v) < 5) return invariantString(roundHalfEven(v, 1) + 0);
  return invariantString(roundHalfEvenInt(v) + 0);
}

/** Won / EV columns: signed bb amount ("+3.2", "-12", "0"). */
export function formatSignedBb(x: number | null | undefined): string {
  if (x === null || x === undefined || Number.isNaN(x)) return '';
  const s = formatBbAmount(x);
  if (s === '0' || s === '-0') return '0';
  return s.startsWith('-') ? s : `+${s}`;
}

/** Range tab "Frequency, %": count / total × 100 as a whole number. */
export function formatFrequency(count: number, total: number): string {
  if (!total) return '0%';
  return `${roundHalfEvenInt((count / total) * 100) + 0}%`;
}

/** Label over the strength bar: "48% weak". Empty when there are no hands. */
export function formatWeak(weak: number, total: number): string {
  if (!total) return '';
  return `${roundHalfEvenInt((weak / total) * 100) + 0}% weak`;
}

/** Range tab counts: 142, 1.3k, 12k, 2.5m. */
export function formatRangeCount(n: number): string {
  return shortenCount(n);
}

/** Bar width in percent of the flex row (the bar shrinks when the label needs room). */
export function barWidthPct(count: number, max: number): number {
  if (!max || count <= 0) return 0;
  return (count / max) * 100;
}

export interface RatioLike {
  cases: number;
  opps: number;
}

export interface RatioDisplay {
  text: string;
  /** Small grey sample number (0 < opps < 15), else null. */
  sampleText: string | null;
  opacity: number;
}

/** A cases/opps ratio with the stat-value rules (popup section 1.2). */
export function formatRatio(r: RatioLike | null | undefined): RatioDisplay {
  const d = resolveCellDisplay(r ? { cases: r.cases, opps: r.opps } : { cases: 0, opps: 0 });
  return { text: d.text, sampleText: d.sampleText, opacity: d.opacity };
}

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

/** "2026-01-23 14:02:31" / ISO → "2026-01-23 14:02". */
export function formatHandDate(s: string | null | undefined): string {
  if (!s) return '';
  return s.replace('T', ' ').slice(0, 16);
}

/** The popup title: the stat's full name with every "->" drawn as an arrow. */
export function popupTitle(name: string): string {
  return name.replaceAll('->', '→');
}
