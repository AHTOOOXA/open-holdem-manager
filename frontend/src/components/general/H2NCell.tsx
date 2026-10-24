import type { CSSProperties, KeyboardEvent } from 'react';
import { cellTooltip, statTitle } from '@/lib/general-titles';
import { cn } from '@/lib/utils';
import { moneyClass } from '@/lib/format';
import { resolveCellDisplay, wireToNumber } from '@/lib/h2n-format';
import type { H2NCellInput } from '@/lib/h2n-format';
import { useStatAppearanceVersion } from '@/lib/format/use-appearance';
import { GENERAL_TONE_CLASS } from '@/lib/h2n-layout';
import type { CellAlign, GeneralCellMeta, GeneralTone } from '@/lib/h2n-layout';

/** Every cell has 4px padding, so an empty cell is an 8x8 box (spacer rows/columns). */
const CELL_BASE = 'flex items-center whitespace-nowrap p-1';

function justify(align: CellAlign | undefined): string {
  return align === 'center' ? 'justify-center' : 'justify-start';
}

function spanStyle(span: number | undefined): CSSProperties | undefined {
  return span && span > 1 ? { gridColumn: `span ${span}` } : undefined;
}

export function H2NEmptyCell({ span }: { span?: number }) {
  return <div aria-hidden className={CELL_BASE} style={spanStyle(span)} />;
}

export function H2NTextCell({
  text,
  tone,
  section,
  align,
  span,
}: {
  text: string;
  tone: GeneralTone;
  section?: boolean;
  align?: CellAlign;
  span?: number;
}) {
  return (
    <div
      className={cn(CELL_BASE, justify(align), GENERAL_TONE_CLASS[tone], section && 'text-lg leading-6')}
      style={spanStyle(span)}
    >
      {text}
    </div>
  );
}

interface H2NStatCellProps {
  meta: GeneralCellMeta;
  data: H2NCellInput | undefined;
  tone: GeneralTone;
  align?: CellAlign;
  span?: number;
  selected: boolean;
  onSelect: (id: string) => void;
  /** Roving tabindex: only the grid's active cell is a tab stop (0), the rest are -1. */
  tabIndex?: number;
  onFocus?: (id: string) => void;
}

/**
 * A stat value with the H2N sample rules: the small sample number for
 * 0 < n < 15 (bottom-aligned, 4px gap), and a dimmed value for n < 10 (drawn
 * in the subtle text level rather than at reduced opacity, so it stays
 * readable). Clicking selects the cell; the selection is the amber selection
 * fill with a primary ring.
 */
export function H2NStatCell({ meta, data, tone, align, span, selected, onSelect, tabIndex = 0, onFocus }: H2NStatCellProps) {
  useStatAppearanceVersion();
  const display = resolveCellDisplay(data, meta.units, { allowVsUser: meta.kind === 'action' });
  const dim = display.opacity < 1;

  // Win rate: money colour of the value (positive / negative / zero).
  let toneClass = GENERAL_TONE_CLASS[tone];
  if (meta.units === 'bb100') toneClass = data ? moneyClass(wireToNumber(data.value)) : GENERAL_TONE_CLASS.winrate;

  const handleKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect(meta.id);
    }
  };

  return (
    <div
      role="button"
      tabIndex={tabIndex}
      aria-pressed={selected}
      aria-label={`${statTitle(meta)}: ${display.text}${display.sampleText ? `, sample ${display.sampleText}` : ''}`}
      title={cellTooltip(meta)}
      data-cell-id={meta.id}
      onClick={() => onSelect(meta.id)}
      onFocus={onFocus ? () => onFocus(meta.id) : undefined}
      onKeyDown={handleKey}
      className={cn(
        CELL_BASE,
        justify(align),
        'relative cursor-pointer rounded-cell outline-none',
        'focus-visible:ring-2 focus-visible:ring-primary',
        selected ? 'bg-selection ring-1 ring-primary ring-inset' : 'hover:bg-overlay-hover',
      )}
      style={spanStyle(span)}
    >
      <span className="flex items-end gap-1">
        <span
          className={cn(
            dim ? 'text-subtle-foreground' : toneClass,
            display.vsUser && 'underline [text-decoration-skip-ink:none]',
          )}
        >
          {display.text}
        </span>
        {display.sampleText && <span className="text-2xs text-sample">{display.sampleText}</span>}
      </span>
    </div>
  );
}
