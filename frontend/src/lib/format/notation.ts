/**
 * Pure notation helpers for the General screen's stat popup and hands list
 * (docs/specs/H2N-COMPATIBLE-STATS.md section 6). No React, no colours.
 */

import { invariantString, resolveCellDisplay, roundHalfEven, roundHalfEvenInt, shortenCount } from './h2n';

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

/** "2026-01-23 14:02:31" / ISO → "2026-01-23 14:02". */
export function formatHandDate(s: string | null | undefined): string {
  if (!s) return '';
  return s.replace('T', ' ').slice(0, 16);
}
