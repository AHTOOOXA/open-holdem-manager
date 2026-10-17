import { cn } from '@/lib/utils';
import type { Strength, StrengthBucket } from '@/lib/api-general';
import { H2N_THEME } from '@/lib/h2n-layout';
import {
  POPUP_THEME,
  barWidthPct,
  formatFrequency,
  formatRangeCount,
  popupTableHeaderStyle,
} from '@/lib/general-notation';

/**
 * Column template shared by the header and the rows (Hand Value | Frequency | Range).
 * The Range column is exactly the bar row's 200px minimum (H2N-COMPATIBLE-STATS.md 6.4);
 * letting it stretch would lengthen every bar and break the clamp below.
 */
const RANGE_ROW_PX = 200;
const COLUMNS = `125px 115px ${RANGE_ROW_PX}px`;

interface RangeTabProps {
  strength: Strength | null;
  selectedKey: string | null;
  onSelect: (bucket: StrengthBucket) => void;
}

/**
 * Range tab (H2N-COMPATIBLE-STATS.md 6.4): one row per hand-value category with its
 * share of the stat's hands and a bar + count. Bars are sized against the
 * biggest category inside a 200px-minimum flex row, so the largest bars all
 * clamp to the same length as in the reference. Rows with no hands stay
 * visible but dimmed and can't be selected.
 */
export default function RangeTab({ strength, selectedKey, onSelect }: RangeTabProps) {
  if (!strength) {
    return <p className="px-4 py-4 text-sm text-white/50">Preflop stats have no hand values.</p>;
  }
  const total = strength.total;
  const max = strength.buckets.reduce((m, b) => Math.max(m, b.count), 0);

  return (
    <div role="listbox" aria-label="Hand values" className="pb-2">
      <div
        className="grid items-center px-4 text-sm"
        style={{ ...popupTableHeaderStyle, gridTemplateColumns: COLUMNS, height: 41 }}
      >
        <span>Hand Value</span>
        <span className="max-w-[78px] truncate" title="Frequency, %">
          Frequency, %
        </span>
        <span>Range</span>
      </div>
      <div className="pt-2">
        {strength.buckets.map((b) => {
          const empty = b.count === 0;
          const selected = selectedKey === b.key;
          return (
            <button
              key={b.key}
              type="button"
              role="option"
              aria-selected={selected}
              disabled={empty}
              title={b.description}
              onClick={() => onSelect(b)}
              className={cn(
                'grid w-full items-center justify-start px-4 text-left text-sm outline-none',
                empty ? 'cursor-default opacity-30' : 'cursor-pointer focus-visible:bg-white/5',
                !selected && !empty && 'hover:bg-white/[0.04]',
              )}
              style={{
                gridTemplateColumns: COLUMNS,
                height: 26.67,
                lineHeight: H2N_THEME.lineHeight,
                fontWeight: empty ? 200 : 400,
                background: selected ? POPUP_THEME.rowSelected : undefined,
                color: '#E8E8E8',
              }}
            >
              <span className="truncate pr-2">{b.label}</span>
              <span>{formatFrequency(b.count, total)}</span>
              <span className="flex items-center gap-2" style={{ width: RANGE_ROW_PX, minWidth: RANGE_ROW_PX }}>
                {!empty && (
                  <>
                    <span
                      aria-hidden
                      className="block h-[6px]"
                      style={{ width: `${barWidthPct(b.count, max)}%`, background: b.color }}
                    />
                    <span className="shrink-0 text-[#D3D3D3]">{formatRangeCount(b.count)}</span>
                  </>
                )}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
