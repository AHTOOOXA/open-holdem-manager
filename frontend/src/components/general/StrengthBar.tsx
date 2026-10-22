import type { Strength, StrengthBucket } from '@/lib/api-general';
import { formatFrequency, formatWeak } from '@/lib/general-notation';
import { hvColor } from '@/lib/hv-color';
import { cn } from '@/lib/utils';

interface StrengthBarProps {
  /** Null or an empty histogram draws the empty bar (the Vs-User row). */
  strength: Strength | null | undefined;
  width?: number | string;
  height?: number;
  /** Key of the selected category: that segment gets the selection ring. */
  selectedKey?: string | null;
  onSelect?: (bucket: StrengthBucket) => void;
  /** Small "48% weak" label (10px instead of 12px), for the table mini bars. */
  compact?: boolean;
}

/**
 * The stacked hand-value bar (H2N-COMPATIBLE-STATS.md 6.1): one segment per category in
 * the Range order, width = share of the hands, colour = category token
 * (hvColor), and a dark "NN% weak" label over its left end. Clicking a segment
 * selects that category.
 */
export default function StrengthBar({
  strength,
  width = 240,
  height = 18,
  selectedKey,
  onSelect,
  compact = false,
}: StrengthBarProps) {
  const total = strength?.total ?? 0;
  if (!strength || total === 0) {
    return (
      <div
        aria-hidden
        className="shrink-0 rounded-cell border border-border bg-overlay-hover"
        style={{ width, height }}
      />
    );
  }

  const weakLabel = formatWeak(strength.weak, total);
  const labelPx = compact ? 10 : 12;
  return (
    <div
      className="relative flex shrink-0 overflow-hidden rounded-cell"
      style={{ width, height }}
      role="group"
      aria-label={`Hand values: ${weakLabel}`}
    >
      {strength.buckets
        .filter((b) => b.count > 0)
        .map((b) => {
          const selected = selectedKey === b.key;
          const title = `${b.label}: ${b.count} (${formatFrequency(b.count, total)})`;
          const style = { width: `${(b.count / total) * 100}%`, background: hvColor(b.key) };
          const ring = selected && 'ring-2 ring-primary ring-inset';
          return onSelect ? (
            <button
              key={b.key}
              type="button"
              title={title}
              aria-label={title}
              aria-pressed={selected}
              className={cn(
                'h-full min-w-0 cursor-pointer p-0 outline-none hover:brightness-110',
                'focus-visible:ring-2 focus-visible:ring-foreground focus-visible:ring-inset',
                ring,
              )}
              style={style}
              onClick={(e) => {
                e.stopPropagation();
                onSelect(b);
              }}
            />
          ) : (
            <div key={b.key} title={title} className={cn('h-full min-w-0', ring)} style={style} />
          );
        })}
      {weakLabel && (
        <span
          className={cn(
            'pointer-events-none absolute top-1/2 left-[3px] -translate-y-1/2 rounded-cell bg-background/75 px-1.5 whitespace-nowrap text-foreground',
            compact ? 'text-2xs' : 'text-xs',
          )}
          style={{ lineHeight: `${Math.max(height - 4, labelPx + 2)}px` }}
        >
          {weakLabel}
        </span>
      )}
    </div>
  );
}
