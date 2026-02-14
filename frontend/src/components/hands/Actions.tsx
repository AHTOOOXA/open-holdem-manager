import type { ActionItem } from '@/lib/api';

export const ACTION_COLORS: Record<string, string> = {
  R: 'text-yellow',
  B: 'text-blue',
  C: 'text-text',
  X: 'text-text-muted',
  F: 'text-text-muted',
};

function formatValue(v: number, precision: number): string {
  if (precision === 0) return Math.round(v).toString();
  const s = v.toFixed(precision);
  // Strip trailing zeros after decimal: "6.0" → "6", "3.50" → "3.5"
  return s.replace(/\.?0+$/, '');
}

/** Plain-text summary for title/tooltip (matches trimFolds + precision logic). */
export function actionTitle(items: ActionItem[], precision: number, trimFolds?: boolean): string {
  if (!items || items.length === 0) return '';
  let display = items;
  if (trimFolds) {
    const firstNonFold = items.findIndex(a => a.a !== 'F');
    if (firstNonFold > 0) display = items.slice(firstNonFold);
  }
  return display.map(a => `${a.a}${a.v != null ? formatValue(a.v, precision) : ''}`).join(' ');
}

export default function Actions({ items, trimFolds, precision = 0 }: { items: ActionItem[]; trimFolds?: boolean; precision?: number }) {
  if (!items || items.length === 0) return null;
  let display = items;
  if (trimFolds) {
    const firstNonFold = items.findIndex((a) => a.a !== 'F');
    if (firstNonFold > 0) display = items.slice(firstNonFold);
  }
  if (display.length === 0) return null;
  return (
    <span className="font-mono text-[15px] whitespace-nowrap">
      {display.map((a, i) => (
        <span key={i}>
          {i > 0 && ' '}
          <span
            className={`${ACTION_COLORS[a.a] || 'text-text'} ${a.h ? 'border-b-2 border-dashed border-current pb-[1px]' : ''}`}
          >
            {a.a}{a.v != null ? formatValue(a.v, precision) : ''}
          </span>
        </span>
      ))}
    </span>
  );
}
