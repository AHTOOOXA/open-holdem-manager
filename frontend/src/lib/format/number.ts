/**
 * App-wide number formatting. One rounding rule everywhere: banker's rounding
 * (half to even, see `roundHalfEven`), never `toFixed` on a raw double.
 * Sign glyphs match the old page-local helpers: ASCII "-" and "+".
 */

import { roundHalfEven, shortenCount } from './h2n';

/** Fixed `digits` decimals, banker's rounding. Never prints "-0.0": a negative that rounds to zero prints unsigned. */
export function fixed(value: number, digits = 0): string {
  if (!Number.isFinite(value)) return String(value);
  const r = roundHalfEven(value, digits);
  return (r === 0 ? 0 : r).toFixed(digits);
}

const GROUPED = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

/** Whole number with thousands separators: grouped(1234567) -> "1,234,567". */
export function grouped(value: number): string {
  return Number.isFinite(value) ? GROUPED.format(value) : String(value);
}

/** `fixed` with trailing zeros stripped: 6.00 -> "6", 3.50 -> "3.5". */
export function trimmed(value: number, digits = 1): string {
  const s = fixed(value, digits);
  return s.includes('.') ? s.replace(/\.?0+$/, '') : s;
}

/** Percent with a "%" sign: pct(12.34) -> "12.3%". */
export function pct(value: number, digits = 1): string {
  return `${fixed(value, digits)}%`;
}

/** Big-blind amount without unit, trailing zeros stripped: bb(6) -> "6", bb(3.5) -> "3.5". */
export function bb(value: number, digits = 2): string {
  return trimmed(value, digits);
}

/** Win rate in bb/100, always two decimals: "1.20". */
export function bb100(value: number): string {
  return fixed(value, 2);
}

/** Dollar amount: usd(-3.5) -> "-$3.50". */
export function usd(value: number, digits = 2): string {
  const s = fixed(Math.abs(value), digits);
  return `${Number(s) === 0 || value >= 0 ? '' : '-'}$${s}`;
}

/** Like `usd` with an explicit "+" on positives: "+$3.50", "-$3.50", "$0.00". */
export function signedUsd(value: number, digits = 2): string {
  const s = usd(value, digits);
  return value > 0 && Number(fixed(value, digits)) !== 0 ? `+${s}` : s;
}

/** Signed number with `digits` decimals: "+1.2", "-1.2", "0.0" (zero is unsigned). */
export function signed(value: number, digits = 1): string {
  const s = fixed(value, digits);
  return Number(s) > 0 ? `+${s}` : s;
}

/** Signed bb amount, `digits` decimals: signedBb(3.25) -> "+3.2". */
export function signedBb(value: number, digits = 1): string {
  return signed(value, digits);
}

/** Hand/opportunity count with k/m shortening: 999, 1.2k, 44k, 2.5m. */
export function count(n: number): string {
  return shortenCount(n);
}

/** Difference b - a, signed, `digits` decimals ("+1.5", "-0.3", "0.0"). */
export function delta(a: number, b: number, digits = 1): string {
  return signed(b - a, digits);
}

export type MoneyTone = 'pos' | 'neg' | 'zero';

/**
 * Colour tone of a money / win-rate value. Zero rule: a value that would
 * display as zero (|v| < half a display unit, i.e. 0.5 * 10^-digits; half a
 * cent for the default 2 digits) is 'zero'; so is NaN. Pass the number of
 * decimals the value is shown with.
 */
export function moneyTone(v: number, digits = 2): MoneyTone {
  if (!Number.isFinite(v)) return 'zero';
  const half = 0.5 * 10 ** -digits;
  if (Math.abs(v) < half) return 'zero';
  return v > 0 ? 'pos' : 'neg';
}

/** Tailwind class for a tone (tokens defined in index.css). */
export function toneClass(tone: MoneyTone): string {
  return tone === 'pos' ? 'text-money-pos' : tone === 'neg' ? 'text-money-neg' : 'text-money-zero';
}

/** Shorthand: toneClass(moneyTone(v, digits)). */
export function moneyClass(v: number, digits = 2): string {
  return toneClass(moneyTone(v, digits));
}

/** bb amount with unit: bbUnits(12.34) -> "12.3 BB". */
export function bbUnits(value: number, digits = 1): string {
  return `${fixed(value, digits)} BB`;
}

/** Duration in seconds as "2h 13m", "13m", "0m" (minutes rounded down). */
export function duration(seconds: number): string {
  const m = Math.max(0, Math.floor(seconds / 60));
  const h = Math.floor(m / 60);
  return h > 0 ? `${h}h ${m % 60}m` : `${m}m`;
}

/** A per-hour figure: 1 decimal under 100, whole above ("540", "61.4"). */
export function rate(value: number): string {
  return Math.abs(value) >= 100 ? fixed(value, 0) : fixed(value, 1);
}

/** File size: bytes(512) -> "512 B", bytes(1536) -> "1.5 KB", bytes(5e9) -> "4.7 GB" (1024-based). */
export function bytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return '--';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return i === 0 ? `${Math.round(v)} B` : `${fixed(v, 1)} ${units[i]}`;
}
