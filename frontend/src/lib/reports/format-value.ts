/** Text of a split-report / spot value by its ValueFormat (all rounding via lib/format). */
import { bb, bb100, count, formatPercent, trimmed, usd } from '@/lib/format';
import type { ValueFormat } from './types';

export const NO_VALUE = '--';

export function formatReportValue(v: number | null | undefined, format: ValueFormat, sample: number | null = null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return NO_VALUE;
  switch (format) {
    case 'count': return count(v);
    case 'pct': return formatPercent(v, sample);
    case 'money': return usd(v);
    case 'bb': return bb(v);
    case 'bbh': return bb(v);
    case 'bb100': return bb100(v);
    case 'ratio': return trimmed(v, 2);
  }
}
