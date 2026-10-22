import { ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { NextActions, Ratio, SplitRow, StrengthBucket } from '@/lib/api-general';
import { POPUP_TABLE_HEADER, formatRatio } from '@/lib/general-notation';
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
  return <span className={d.opacity < 1 ? 'text-subtle-foreground' : undefined}>{d.text}</span>;
}

function NextGroup({ items }: { items: Ratio[] }) {
  return (
    <span className="whitespace-nowrap">
      {items.map((r, i) => (
        <span key={i}>
          {i > 0 && <span className="text-subtle-foreground">/</span>}
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
    return <p className="px-4 py-4 text-sm text-muted-foreground">{emptyText}</p>;
  }

  return (
    // Plain rows rather than a listbox: each row has its own select button and
    // (with a Range column) separate segment buttons, and options must not
    // contain interactive children.
    <div role="group" aria-label={headerLabel} className="pb-2">
      <div
        className={cn('grid items-center gap-x-1 px-4 text-sm', POPUP_TABLE_HEADER)}
        style={{ gridTemplateColumns: columns, height: 41 }}
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
                'grid h-row-dense w-full items-center gap-x-1 px-4 text-sm leading-4.5 text-foreground',
                disabled ? 'cursor-default opacity-30' : 'cursor-pointer',
                selected ? 'bg-selection' : !disabled && 'hover:bg-overlay-hover',
              )}
              style={{ gridTemplateColumns: columns }}
            >
              <button
                type="button"
                disabled={disabled}
                aria-pressed={selected}
                aria-label={`${row.label}: ${freq.text}${freq.text === '--' ? '' : '%'}, ${row.cases} of ${row.opps}`}
                title={row.label}
                className="min-w-0 truncate rounded-cell text-left outline-none enabled:cursor-pointer focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-default"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectRow(row);
                }}
              >
                {row.label}
              </button>
              <span aria-hidden className="flex items-end gap-1">
                <span className={freq.opacity < 1 ? 'text-subtle-foreground' : undefined}>{freq.text}</span>
                {freq.sampleText && <span className="text-2xs text-sample">{freq.sampleText}</span>}
              </span>
              {showRange && (
                <span className="flex min-w-0 items-center pr-1">
                  {row.strength && row.strength.total > 0 && (
                    <StrengthBar
                      strength={row.strength}
                      width="100%"
                      height={14}
                      compact
                      selectedKey={selected ? (selection?.bucket ?? null) : null}
                      onSelect={disabled ? undefined : (b) => onSelectSegment(row, b)}
                    />
                  )}
                </span>
              )}
              <ArrowRight aria-hidden className="size-3.5 text-subtle-foreground" />
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
