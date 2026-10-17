import type { Strength, StrengthBucket } from '@/lib/api-general';
import { POPUP_THEME, formatFrequency, formatWeak } from '@/lib/general-notation';

interface StrengthBarProps {
  /** Null or an empty histogram draws the empty grey bar (the Vs-User row). */
  strength: Strength | null | undefined;
  width?: number | string;
  height?: number;
  /** Key of the selected category: that segment gets the yellow frame. */
  selectedKey?: string | null;
  onSelect?: (bucket: StrengthBucket) => void;
  /** Size of the "48% weak" label. */
  labelSize?: number;
}

/**
 * The stacked hand-value bar (H2N-COMPATIBLE-STATS.md 6.1): one segment per category in
 * the Range order, width = share of the hands, colour = category colour, and a
 * dark "NN% weak" label over its left end. Clicking a segment selects that
 * category.
 */
export default function StrengthBar({
  strength,
  width = 240,
  height = 18,
  selectedKey,
  onSelect,
  labelSize = 12,
}: StrengthBarProps) {
  const total = strength?.total ?? 0;
  if (!strength || total === 0) {
    return (
      <div
        aria-hidden
        className="shrink-0 rounded-[2px]"
        style={{
          width,
          height,
          background: POPUP_THEME.emptyBar,
          border: `1px solid ${POPUP_THEME.emptyBarBorder}`,
        }}
      />
    );
  }

  const weakLabel = formatWeak(strength.weak, total);
  return (
    <div
      className="relative flex shrink-0 overflow-hidden rounded-[2px]"
      style={{ width, height }}
      role="group"
      aria-label={`Hand values: ${weakLabel}`}
    >
      {strength.buckets
        .filter((b) => b.count > 0)
        .map((b) => {
          const selected = selectedKey === b.key;
          const title = `${b.label}: ${b.count} (${formatFrequency(b.count, total)})`;
          const style = {
            width: `${(b.count / total) * 100}%`,
            background: b.color,
            boxShadow: selected ? `inset 0 0 0 1.5px ${POPUP_THEME.segmentOutline}` : undefined,
          };
          return onSelect ? (
            <button
              key={b.key}
              type="button"
              title={title}
              aria-label={title}
              aria-pressed={selected}
              className="h-full min-w-0 cursor-pointer p-0 outline-none hover:brightness-110 focus-visible:brightness-125"
              style={style}
              onClick={(e) => {
                e.stopPropagation();
                onSelect(b);
              }}
            />
          ) : (
            <div key={b.key} title={title} className="h-full min-w-0" style={style} />
          );
        })}
      {weakLabel && (
        <span
          className="pointer-events-none absolute top-1/2 left-[3px] -translate-y-1/2 rounded-[3px] px-1.5 whitespace-nowrap text-white"
          style={{
            background: POPUP_THEME.weakPill,
            fontSize: labelSize,
            lineHeight: `${Math.max(height - 4, labelSize + 2)}px`,
          }}
        >
          {weakLabel}
        </span>
      )}
    </div>
  );
}
