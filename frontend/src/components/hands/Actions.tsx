import type { ActionItem } from '@/lib/api';
import { bb } from '@/lib/format';

export const ACTION_COLORS: Record<string, string> = {
  R: 'text-yellow',
  B: 'text-blue',
  C: 'text-text',
  X: 'text-text-muted',
  F: 'text-text-muted',
};

/** Format a BB amount. Precision 1 keeps 2.5bb opens readable; trailing ".0" is dropped. */
export function formatBb(v: number, precision: number): string {
  // Trailing zeros stripped: "6.0" → "6", "3.50" → "3.5"
  return bb(v, precision);
}

/** Plain-text summary for title/tooltip (matches trimFolds + precision logic). */
export function actionTitle(items: ActionItem[], precision: number, trimFolds?: boolean): string {
  if (!items || items.length === 0) return '';
  let display = items;
  if (trimFolds) {
    const firstNonFold = items.findIndex(a => a.a !== 'F');
    if (firstNonFold > 0) display = items.slice(firstNonFold);
  }
  return display.map(a => `${a.a}${a.v != null ? formatBb(a.v, precision) : ''}`).join(' ');
}

export default function Actions({ items, trimFolds, precision = 1 }: { items: ActionItem[]; trimFolds?: boolean; precision?: number }) {
  if (!items || items.length === 0) return null;
  let display = items;
  if (trimFolds) {
    const firstNonFold = items.findIndex((a) => a.a !== 'F');
    if (firstNonFold > 0) display = items.slice(firstNonFold);
  }
  if (display.length === 0) return null;
  return (
    <span className="text-[15px] whitespace-nowrap">
      {display.map((a, i) => (
        <span key={i}>
          {i > 0 && ' '}
          <span
            className={`${ACTION_COLORS[a.a] || 'text-text'} ${a.h ? 'border-b-2 border-dashed border-current pb-[1px]' : ''}`}
          >
            {a.a}{a.v != null ? formatBb(a.v, precision) : ''}
          </span>
        </span>
      ))}
    </span>
  );
}
