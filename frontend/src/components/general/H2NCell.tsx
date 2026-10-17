import type { CSSProperties, KeyboardEvent } from 'react';
import { cellTooltip, statTitle } from '@/lib/general-titles';
import { cn } from '@/lib/utils';
import { resolveCellDisplay, wireToNumber } from '@/lib/h2n-format';
import type { H2NCellInput } from '@/lib/h2n-format';
import {
  H2N_COLORS,
  H2N_THEME,
  H2N_WINRATE_NEGATIVE,
} from '@/lib/h2n-layout';
import type { CellAlign, GeneralCellMeta, H2NColorKey } from '@/lib/h2n-layout';

/** Every cell has 4px padding, so an empty cell is an 8x8 box (spacer rows/columns). */
const cellBase: CSSProperties = {
  padding: H2N_THEME.cellPadding,
  display: 'flex',
  alignItems: 'center',
  whiteSpace: 'nowrap',
};

function justify(align: CellAlign | undefined): CSSProperties['justifyContent'] {
  return align === 'center' ? 'center' : 'flex-start';
}

function spanStyle(span: number | undefined): CSSProperties | undefined {
  return span && span > 1 ? { gridColumn: `span ${span}` } : undefined;
}

export function H2NEmptyCell({ span }: { span?: number }) {
  return <div aria-hidden style={{ ...cellBase, ...spanStyle(span) }} />;
}

export function H2NTextCell({
  text,
  color,
  section,
  align,
  span,
}: {
  text: string;
  color: H2NColorKey;
  section?: boolean;
  align?: CellAlign;
  span?: number;
}) {
  return (
    <div
      style={{
        ...cellBase,
        ...spanStyle(span),
        justifyContent: justify(align),
        color: H2N_COLORS[color],
        fontSize: section ? H2N_THEME.sectionFontSize : undefined,
        lineHeight: section ? H2N_THEME.sectionLineHeight : undefined,
      }}
    >
      {text}
    </div>
  );
}

interface H2NStatCellProps {
  meta: GeneralCellMeta;
  data: H2NCellInput | undefined;
  color: H2NColorKey;
  align?: CellAlign;
  span?: number;
  selected: boolean;
  onSelect: (id: string) => void;
  /** Roving tabindex: only the grid's active cell is a tab stop (0), the rest are -1. */
  tabIndex?: number;
  onFocus?: (id: string) => void;
}

/**
 * A stat value with the H2N sample rules: the small grey sample number for
 * 0 < n < 15 (bottom-aligned, 4px gap), and 50% opacity for n < 10, with the
 * sample dimmed once more on top. Clicking selects the cell; the selection is
 * a translucent yellow overlay over the whole cell.
 */
export function H2NStatCell({ meta, data, color, align, span, selected, onSelect, tabIndex = 0, onFocus }: H2NStatCellProps) {
  const display = resolveCellDisplay(data, meta.units, { allowVsUser: meta.kind === 'action' });

  // Win rate: the reference colour is for a positive number; use red for a loss.
  let textColor = H2N_COLORS[color];
  if (meta.units === 'bb100' && data) {
    const v = wireToNumber(data.value);
    if (v < 0) textColor = H2N_WINRATE_NEGATIVE;
  }

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
        'relative cursor-pointer rounded-[2px] outline-none',
        'focus-visible:ring-1 focus-visible:ring-white/30',
        !selected && 'hover:bg-[rgba(255,255,130,0.06)]',
      )}
      style={{ ...cellBase, ...spanStyle(span), justifyContent: justify(align) }}
    >
      <span className="flex items-end gap-1" style={{ opacity: display.opacity }}>
        <span
          style={{
            color: textColor,
            textDecoration: display.vsUser ? 'underline' : undefined,
            textDecorationSkipInk: display.vsUser ? 'none' : undefined,
          }}
        >
          {display.text}
        </span>
        {display.sampleText && (
          <span
            style={{
              fontSize: H2N_THEME.sampleFontSize,
              lineHeight: 'normal',
              color: H2N_THEME.sample,
              opacity: display.opacity,
            }}
          >
            {display.sampleText}
          </span>
        )}
      </span>
      {selected && (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-[2px]"
          style={{ background: H2N_THEME.selectedOverlay }}
        />
      )}
    </div>
  );
}
