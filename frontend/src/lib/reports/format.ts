/** Display of Reports stat values by the contract's `ValueFormat`. */
import { bb, bb100, duration, formatBb100, formatHands, formatPercent, moneyTone, rate, usd } from '@/lib/format';
import type { MoneyTone } from '@/lib/format';
import type { ValueFormat } from './types';

/** Text for a stat value. null / non-finite -> "--". `sample` feeds the percent rule (no value below 1 opportunity). */
export function formatSpotValue(value: number | null | undefined, format: ValueFormat, sample: number | null = null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '--';
  switch (format) {
    case 'count':
      return formatHands(value);
    case 'pct':
      return formatPercent(value, sample);
    case 'money':
      return usd(value);
    case 'bb':
      return bb(value, 1);
    case 'bb100':
      return formatBb100(value);
    case 'bbh':
      return bb(value, 2);
    case 'ratio':
      return bb100(value);
    case 'duration':
      return duration(value);
    case 'rate':
      return rate(value);
  }
}

/** Money tone for winnings values; null for the rest and for missing values. */
export function spotTone(value: number | null | undefined, winnings: boolean | undefined, format: ValueFormat): MoneyTone | null {
  if (!winnings || value === null || value === undefined) return null;
  return moneyTone(value, format === 'money' ? 2 : 1);
}
