/**
 * Number formatting and sample-size rules for the H2N-style General screen.
 *
 * Pure functions only (no React), so they can be checked from a plain node
 * script. Behaviour follows docs/specs/H2N-COMPATIBLE-STATS.md §3:
 *
 * - percent stats: `--` for no sample, `99` for an exact 100, one decimal
 *   inside (-10, 10), integers otherwise, truncated + shortened above 100;
 * - bb/100: two decimals inside (-1, 1), one inside (-10, 10), then an integer
 *   that goes through the "amount" shortener;
 * - hand counts: 1.2k / 44k / 1.2m style shortening;
 * - rounding is banker's rounding (half to even) on the exact double, the way
 *   .NET's Math.Round works. `toFixed` must not be used: it rounds the decimal
 *   string half away from zero, which gives different strings at midpoints.
 */

/** Comparison tolerance used by every threshold check. */
export const H2N_EPS = 1e-6;

/** Appearance defaults (not user-editable on this screen). */
export const H2N_APPEARANCE = {
  /** Show the small grey sample number when 0 < sample < this. */
  showSampleThreshold: 15,
  /** Dim the value when sample < this (sample 0 included). */
  transparentThreshold: 10,
  /** Opacity applied to a small-sample value (the sample gets it twice). */
  smallSampleOpacity: 0.5,
  /** Show the vs-user value instead of the overall one when vsUserSample > this. 0 disables. */
  substituteByVsUserThreshold: 50,
  /** One decimal is shown strictly inside (-this, this). */
  oneDecimalThreshold: 10,
} as const;

export type H2NUnits = 'percent' | 'bb100' | 'count';

// ── Low-level helpers ──────────────────────────────────────────────

function greater(a: number, b: number): boolean {
  return a - b > H2N_EPS;
}

function less(a: number, b: number): boolean {
  return b - a > H2N_EPS;
}

function nearlyEqual(a: number, b: number): boolean {
  return Math.abs(a - b) < H2N_EPS;
}

/** Round to the nearest integer; exact .5 goes to the even neighbour. Keeps the sign of zero. */
export function roundHalfEvenInt(x: number): number {
  if (!Number.isFinite(x)) return x;
  const floor = Math.floor(x);
  const frac = x - floor; // exact for doubles of this magnitude
  let r: number;
  if (frac > 0.5) r = floor + 1;
  else if (frac < 0.5) r = floor;
  else r = floor % 2 === 0 ? floor : floor + 1;
  // Rounding a negative number up to zero yields -0, like a sign-preserving round.
  if (r === 0 && (x < 0 || Object.is(x, -0))) return -0;
  return r;
}

/**
 * Round to `digits` decimals with banker's rounding: scale by 10^digits,
 * round the scaled double half-to-even, scale back. This mirrors how the
 * reference implementation rounds, including its behaviour on doubles that are
 * not exactly representable (e.g. 0.25 → 0.2, 0.75 → 0.8).
 */
export function roundHalfEven(x: number, digits = 0): number {
  if (digits === 0) return roundHalfEvenInt(x);
  const p = 10 ** digits;
  return roundHalfEvenInt(x * p) / p;
}

/**
 * Culture-invariant number to string: shortest round-trip form, no trailing
 * zeros, and a negative zero prints as "-0" (as the reference runtime does).
 */
export function invariantString(x: number): string {
  if (Object.is(x, -0)) return '-0';
  return String(x);
}

/** Shorten an integer count: 999 → "999", 1250 → "1.2k", 44500 → "44k", 2.5m → "2.5m". */
export function shortenCount(value: number): string {
  const v = Math.trunc(value);
  const abs = Math.abs(v);
  if (abs < 1_000_000) {
    if (abs >= 1000) {
      if (abs < 10_000) return invariantString(roundHalfEven(v / 1000, 1)) + 'k';
      return invariantString(roundHalfEven(v / 1000)) + 'k';
    }
    return invariantString(v === 0 ? 0 : v);
  }
  if (abs < 10_000_000) return invariantString(roundHalfEven(v / 1_000_000, 1)) + 'm';
  return invariantString(roundHalfEven(v / 1_000_000)) + 'm';
}

/** True when `value / divider` is (within tolerance) a whole number. */
function isMultipleOf(value: number, divider: number): boolean {
  const q = value / divider;
  return nearlyEqual(q, Math.trunc(q));
}

/**
 * Shorten an amount (already rounded by the caller for bb/100):
 * < 100 as is; < 1000 one decimal; < 10k "1.2k" only for multiples of 100,
 * otherwise the rounded integer; < 100k "12.3k"; < 1m "123k"; then "m".
 */
export function shortenAmount(amount: number): string {
  const abs = Math.abs(amount);
  if (abs < 100) return invariantString(amount);
  if (abs < 1000) return invariantString(roundHalfEven(amount, 1));
  if (abs < 10_000) {
    if (isMultipleOf(amount, 100)) return invariantString(roundHalfEven(amount / 1000, 1)) + 'k';
    return invariantString(roundHalfEven(amount));
  }
  if (abs < 100_000) return invariantString(roundHalfEven(amount / 1000, 1)) + 'k';
  if (abs < 1_000_000) return invariantString(roundHalfEven(amount / 1000)) + 'k';
  if (abs < 10_000_000) return invariantString(roundHalfEven(amount / 1_000_000, 2)) + 'm';
  return invariantString(roundHalfEven(amount / 1_000_000)) + 'm';
}

function infinityString(x: number): string {
  return x > 0 ? '∞' : '-∞';
}

// ── Value computation ──────────────────────────────────────────────

/**
 * Percentage of an action stat. The operation order matters for which side of
 * a .5 midpoint the double lands on: divide first, then multiply by 100
 * (23/40 → 57.49999999999999 → "57", whereas 2300/40 = 57.5 → "58").
 * Returns NaN for 0 opportunities.
 */
export function actionPercent(cases: number, opps: number): number {
  return (cases / opps) * 100.0;
}

// ── Formatters ─────────────────────────────────────────────────────

/**
 * Format a percent-unit stat. `sample` = opportunities (or the expression's
 * largest referenced sample); pass `null` when the stat has no sample at all.
 */
export function formatPercent(value: number | null | undefined, sample: number | null = null): string {
  if (sample === 0) return '--';
  if (value === null || value === undefined || Number.isNaN(value)) return '--';
  if (!Number.isFinite(value)) return infinityString(value);
  if (value < -100 || value > 100) return shortenCount(Math.trunc(value));
  if (nearlyEqual(value, 100)) return '99';
  const t = H2N_APPEARANCE.oneDecimalThreshold;
  if (greater(value, -t) && less(value, t)) return invariantString(roundHalfEven(value, 1));
  return invariantString(roundHalfEven(value));
}

/** Format a win rate in bb/100. NaN/null (no hands) → "--". */
export function formatBb100(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '--';
  if (!Number.isFinite(value)) return infinityString(value);
  if (greater(value, -1) && less(value, 1)) return invariantString(roundHalfEven(value, 2));
  if (greater(value, -10) && less(value, 10)) return invariantString(roundHalfEven(value, 1));
  return shortenAmount(roundHalfEven(value));
}

/** Format a hand count: 999 → "999", 1250 → "1.2k", 44 499 → "44k". */
export function formatHands(count: number | null | undefined): string {
  if (count === null || count === undefined || Number.isNaN(count)) return '--';
  if (!Number.isFinite(count)) return infinityString(count);
  return shortenCount(count);
}

export function formatStatValue(
  value: number | null | undefined,
  units: H2NUnits,
  sample: number | null = null,
): string {
  if (units === 'bb100') return sample === 0 ? '--' : formatBb100(value);
  if (units === 'count') return formatHands(value);
  return formatPercent(value, sample);
}

// ── Sample size display ────────────────────────────────────────────

/** Whether the small grey sample number is shown after the value. */
export function shouldShowSample(sample: number | null | undefined): boolean {
  return sample != null && sample > 0 && sample < H2N_APPEARANCE.showSampleThreshold;
}

/** Whether the value is drawn at reduced opacity. `null` sample = never dimmed. */
export function shouldDim(sample: number | null | undefined): boolean {
  return sample != null && sample < H2N_APPEARANCE.transparentThreshold;
}

/** Opacity of the value group (the sample span gets the same factor again on top). */
export function sampleOpacity(sample: number | null | undefined): number {
  return shouldDim(sample) ? H2N_APPEARANCE.smallSampleOpacity : 1;
}

// ── Cell resolution ────────────────────────────────────────────────

/** Infinity can't travel through JSON, so the API spells it out. null = NaN / no value. */
export type WireNumber = number | 'inf' | '-inf' | null;

export interface H2NCellInput {
  value?: WireNumber;
  sample?: number | null;
  cases?: number;
  opps?: number;
  vs_user?: { value?: WireNumber; sample: number; cases?: number; opps?: number } | null;
}

export interface H2NCellDisplay {
  /** Formatted value ("26", "9.5", "--", "∞", ...). */
  text: string;
  /** Sample to print in the small grey span, or null when hidden. */
  sampleText: string | null;
  /** Opacity of the value group. */
  opacity: number;
  /** The vs-user value replaced the overall value (rendered underlined). */
  vsUser: boolean;
}

export function wireToNumber(v: WireNumber | undefined): number {
  if (v === 'inf') return Infinity;
  if (v === '-inf') return -Infinity;
  if (v === null || v === undefined) return NaN;
  return v;
}

/**
 * Numeric value of a cell: prefer raw counters (so the division happens in the
 * exact reference order on this side too), else the precomputed value.
 */
export function cellNumber(input: { value?: WireNumber; cases?: number; opps?: number }): number {
  if (typeof input.cases === 'number' && typeof input.opps === 'number') {
    return actionPercent(input.cases, input.opps);
  }
  return wireToNumber(input.value);
}

function cellSample(input: { sample?: number | null; opps?: number }): number | null {
  if (input.sample !== undefined) return input.sample;
  if (typeof input.opps === 'number') return input.opps;
  return null;
}

/**
 * Everything a stat cell needs to render. For `count` units (Hands) the value
 * itself drives dimming and no sample is printed.
 */
export function resolveCellDisplay(
  input: H2NCellInput | null | undefined,
  units: H2NUnits = 'percent',
  options: { allowVsUser?: boolean } = {},
): H2NCellDisplay {
  if (!input) return { text: '--', sampleText: null, opacity: sampleOpacity(0), vsUser: false };

  if (units === 'count') {
    const n = cellNumber(input);
    return { text: formatHands(n), sampleText: null, opacity: sampleOpacity(Number.isNaN(n) ? 0 : n), vsUser: false };
  }

  const threshold = H2N_APPEARANCE.substituteByVsUserThreshold;
  const vs = input.vs_user;
  const useVs = (options.allowVsUser ?? true) && threshold > 0 && vs != null && vs.sample > threshold;
  const src = useVs && vs ? vs : input;
  const value = cellNumber(src);
  const sample = cellSample(src);

  return {
    text: formatStatValue(value, units, sample),
    sampleText: shouldShowSample(sample) ? String(sample) : null,
    opacity: sampleOpacity(sample),
    vsUser: useVs,
  };
}
