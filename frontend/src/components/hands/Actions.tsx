import type { ActionItem } from '@/lib/api';

export const ACTION_COLORS: Record<string, string> = {
  R: 'text-yellow',
  B: 'text-blue',
  C: 'text-text',
  X: 'text-text-muted',
  F: 'text-text-muted',
};

export default function Actions({ items, trimFolds }: { items: ActionItem[]; trimFolds?: boolean }) {
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
            {a.a}{a.v != null ? a.v : ''}
          </span>
        </span>
      ))}
    </span>
  );
}
