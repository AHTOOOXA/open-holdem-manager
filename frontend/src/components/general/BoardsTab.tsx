import { ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { NextActions, Ratio, SplitRow, StrengthBucket } from '@/lib/api-general';
import { H2N_THEME } from '@/lib/h2n-layout';
import { POPUP_THEME, formatRatio, popupTableHeaderStyle } from '@/lib/general-notation';
import StrengthBar from './StrengthBar';

/** Selected row (and optionally a hand-value segment inside its mini bar). */
export interface SplitSelection {
  rowKey: string;
  bucket?: string;
}

interface SplitTableProps {
  rows: SplitRow[];
  /** First column header: "Board" or "Bet Size". */
  headerLabel: string;
  /** Preflop bet sizes have no hand values, so no Range column. */
  showRange: boolean;
  selection: SplitSelection | null;
  onSelectRow: (row: SplitRow) => void;
  onSelectSegment: (row: SplitRow, bucket: StrengthBucket) => void;
  emptyText: string;
}

function NextValue({ r }: { r: Ratio }) {
  const d = formatRatio(r);
  return <span style={{ opacity: d.opacity }}>{d.text}</span>;
}

function NextGroup({ items }: { items: Ratio[] }) {
  return (
    <span className="whitespace-nowrap">
      {items.map((r, i) => (
        <span key={i}>
          {i > 0 && <span className="text-white/40">/</span>}
          <NextValue r={r} />
        </span>
      ))}
    </span>
  );
}

function nextCells(next: NextActions) {
  return {
    fcr: next.show_fold_call_raise ? <NextGroup items={[next.fold, next.call, next.raise]} /> : null,
    bx: next.show_bet_check ? <NextGroup items={[next.bet, next.check]} /> : null,
  };
}

/**
 * The Boards / Bet Sizes table (H2N-COMPATIBLE-STATS.md 6.5, 6.6): the stat's frequency
 * on that slice, a mini strength bar of its hands, and hero's next decision
 * as "Fold/Call/Raise" and "Bet/Check". The Action Profit column is left out
 * (not in the reference screenshot). Rows without cases are dimmed and can't
 * be selected.
 */
export function SplitTable({
  rows,
  headerLabel,
  showRange,
  selection,
  onSelectRow,
  onSelectSegment,
  emptyText,
}: SplitTableProps) {
  const columns = showRange
    ? '96px 74px minmax(100px, 1fr) 18px 84px 58px'
    : '120px 90px 18px 96px 70px';

  if (rows.length === 0) {
    return <p className="px-4 py-4 text-sm text-white/50">{emptyText}</p>;
  }

  return (
    // Plain rows rather than a listbox: each row has its own select button and
    // (with a Range column) separate segment buttons, and options must not
    // contain interactive children.
    <div role="group" aria-label={headerLabel} className="pb-2">
      <div
        className="grid items-center gap-x-1 px-4 text-sm"
        style={{ ...popupTableHeaderStyle, gridTemplateColumns: columns, height: 41 }}
      >
        <span className="truncate">{headerLabel}</span>
        <span className="truncate" title="Frequency, %">
          Frequency, %
        </span>
        {showRange && <span>Range</span>}
        <span aria-hidden />
        <span className="truncate" title="Fold/Call/Raise Next">
          Fold/Call/Raise Next
        </span>
        <span className="truncate" title="Bet/Check Next">
          Bet/Check Next
        </span>
      </div>
      <div className="pt-2">
        {rows.map((row) => {
          const freq = formatRatio(row);
          const disabled = row.cases === 0;
          const selected = selection?.rowKey === row.key;
          const { fcr, bx } = nextCells(row.next);
          return (
            <div
              key={row.key}
              // Mouse convenience: the whole row selects. Keyboard / AT use the label button.
              onClick={() => !disabled && onSelectRow(row)}
              className={cn(
                'grid w-full items-center gap-x-1 px-4 text-sm',
                disabled ? 'cursor-default opacity-30' : 'cursor-pointer focus-within:bg-white/5',
                !selected && !disabled && 'hover:bg-white/[0.04]',
              )}
              style={{
                gridTemplateColumns: columns,
                height: 26.67,
                lineHeight: H2N_THEME.lineHeight,
                background: selected ? POPUP_THEME.rowSelected : undefined,
                color: '#E8E8E8',
              }}
            >
              <button
                type="button"
                disabled={disabled}
                aria-pressed={selected}
                aria-label={`${row.label}: ${freq.text}${freq.text === '--' ? '' : '%'}, ${row.cases} of ${row.opps}`}
                title={row.label}
                className="min-w-0 truncate rounded-[2px] text-left outline-none enabled:cursor-pointer focus-visible:ring-1 focus-visible:ring-white/40 disabled:cursor-default"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectRow(row);
                }}
              >
                {row.label}
              </button>
              <span aria-hidden className="flex items-end gap-1" style={{ opacity: freq.opacity }}>
                <span>{freq.text}</span>
                {freq.sampleText && (
                  <span style={{ fontSize: H2N_THEME.sampleFontSize, color: H2N_THEME.sample, lineHeight: 'normal' }}>
                    {freq.sampleText}
                  </span>
                )}
              </span>
              {showRange && (
                <span className="flex min-w-0 items-center pr-1">
                  {row.strength && row.strength.total > 0 && (
                    <StrengthBar
                      strength={row.strength}
                      width="100%"
                      height={14}
                      labelSize={10}
                      selectedKey={selected ? (selection?.bucket ?? null) : null}
                      onSelect={disabled ? undefined : (b) => onSelectSegment(row, b)}
                    />
                  )}
                </span>
              )}
              <ArrowRight aria-hidden className="size-3.5 text-white/30" />
              <span>{fcr}</span>
              <span>{bx}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface BoardsTabProps {
  rows: SplitRow[];
  selection: SplitSelection | null;
  onSelectRow: (row: SplitRow) => void;
  onSelectSegment: (row: SplitRow, bucket: StrengthBucket) => void;
}

/** Boards tab: the stat split by board texture of the stat street (rows can overlap). */
export default function BoardsTab(props: BoardsTabProps) {
  return <SplitTable {...props} headerLabel="Board" showRange emptyText="No boards for this stat." />;
}
