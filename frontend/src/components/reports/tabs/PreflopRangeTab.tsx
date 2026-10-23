import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPreflopRange, queryKeyOf } from '@/lib/reports/api';
import type { RangeCell, ReportQuery } from '@/lib/reports/types';
import {
  GRID_SIZE,
  classAt,
  moveFocus,
  rectClasses,
  toggleClass,
  unionClasses,
  type GridPos,
} from '@/lib/reports/range-grid';
import { rangeLevelShade } from '@/lib/chart-theme';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { count, formatSignedBb, moneyClass } from '@/lib/format';
import { cn } from '@/lib/utils';

interface PreflopRangeTabProps {
  query: ReportQuery;
  /** Selected hand classes ("AKs", "QQ"). */
  selected: string[];
  onSelect: (cells: string[]) => void;
}

type Metric = 'count' | 'won';

const GRID_POSITIONS: GridPos[] = Array.from({ length: GRID_SIZE * GRID_SIZE }, (_, i) => ({
  row: Math.floor(i / GRID_SIZE),
  col: i % GRID_SIZE,
}));

/** Preflop Range upper tab: 13x13 grid shaded by frequency level; click, shift-click, drag or keys select classes. */
export default function PreflopRangeTab({ query, selected, onSelect }: PreflopRangeTabProps) {
  const [metric, setMetric] = useState<Metric>('count');
  const [focus, setFocus] = useState<GridPos>({ row: 0, col: 0 });
  const [drag, setDrag] = useState<{ anchor: GridPos; over: GridPos } | null>(null);
  const lastClicked = useRef<GridPos | null>(null);
  const cellRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['reports', 'preflop-range', queryKeyOf(query)],
    queryFn: ({ signal }) => getPreflopRange(query, signal),
  });

  const byClass = useMemo(() => {
    const m = new Map<string, RangeCell>();
    for (const c of data?.cells ?? []) m.set(c.cls, c);
    return m;
  }, [data]);

  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const preview = useMemo(() => (drag ? new Set(rectClasses(drag.anchor, drag.over)) : null), [drag]);

  const finishDrag = useCallback(
    (d: { anchor: GridPos; over: GridPos }, additive: boolean) => {
      setDrag(null);
      const sameCell = d.anchor.row === d.over.row && d.anchor.col === d.over.col;
      if (sameCell) {
        const cls = classAt(d.anchor.row, d.anchor.col);
        if (additive && lastClicked.current) {
          onSelect(unionClasses(selected, rectClasses(lastClicked.current, d.anchor)));
        } else {
          onSelect(toggleClass(selected, cls));
        }
        lastClicked.current = d.anchor;
      } else {
        const rect = rectClasses(d.anchor, d.over);
        onSelect(additive ? unionClasses(selected, rect) : rect);
        lastClicked.current = d.anchor;
      }
    },
    [onSelect, selected],
  );

  // End the drag wherever the pointer is released
  const additiveRef = useRef(false);
  useEffect(() => {
    if (!drag) return;
    const up = () => finishDrag(drag, additiveRef.current);
    window.addEventListener('pointerup', up);
    return () => window.removeEventListener('pointerup', up);
  }, [drag, finishDrag]);

  const focusCell = (pos: GridPos) => {
    setFocus(pos);
    cellRefs.current[pos.row * GRID_SIZE + pos.col]?.focus();
  };

  const onKeyDown = (e: React.KeyboardEvent, pos: GridPos) => {
    if (e.key.startsWith('Arrow')) {
      e.preventDefault();
      focusCell(moveFocus(pos, e.key));
    } else if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      onSelect(toggleClass(selected, classAt(pos.row, pos.col)));
      lastClicked.current = pos;
    } else if (e.key === 'Escape' && selected.length) {
      onSelect([]);
    }
  };

  if (isPending) {
    return (
      <div className="p-3" aria-busy>
        <Skeleton className="aspect-square w-full max-w-xl" />
      </div>
    );
  }
  if (isError) {
    return (
      <p role="alert" className="p-4 text-sm text-money-neg">
        Failed to load range{error instanceof Error ? `: ${error.message}` : ''}
      </p>
    );
  }
  if (data.total === 0) return <p className="p-4 text-sm text-muted-foreground">No hands match this page.</p>;

  return (
    <div className="flex flex-col gap-2 p-3">
      <div className="flex items-center gap-3">
        <ToggleGroup type="single" value={metric} onValueChange={(v) => v && setMetric(v as Metric)} aria-label="Cell value">
          <ToggleGroupItem value="count" className="h-control px-3 text-xs">
            Count
          </ToggleGroupItem>
          <ToggleGroupItem value="won" className="h-control px-3 text-xs">
            Won
          </ToggleGroupItem>
        </ToggleGroup>
        <span className="text-xs text-muted-foreground">{count(data.total)} hands</span>
        {selected.length > 0 && (
          <Button variant="ghost" size="sm" className="ml-auto" onClick={() => onSelect([])}>
            Clear ({selected.length})
          </Button>
        )}
      </div>
      <div
        role="grid"
        aria-label="Preflop range"
        aria-multiselectable
        className="grid w-full max-w-xl select-none gap-px"
        style={{ gridTemplateColumns: `repeat(${GRID_SIZE}, minmax(0, 1fr))` }}
      >
        {GRID_POSITIONS.map((pos) => {
          const cls = classAt(pos.row, pos.col);
          const cell = byClass.get(cls);
          const isSelected = preview ? preview.has(cls) : selectedSet.has(cls);
          const empty = !cell || cell.hands === 0;
          const i = pos.row * GRID_SIZE + pos.col;
          return (
            <button
              key={cls}
              ref={(el) => {
                cellRefs.current[i] = el;
              }}
              type="button"
              role="gridcell"
              aria-selected={isSelected}
              aria-label={`${cls}: ${cell?.hands ?? 0} hands`}
              tabIndex={focus.row === pos.row && focus.col === pos.col ? 0 : -1}
              onFocus={() => setFocus(pos)}
              onKeyDown={(e) => onKeyDown(e, pos)}
              onPointerDown={(e) => {
                if (e.button !== 0) return;
                e.preventDefault();
                additiveRef.current = e.shiftKey;
                setFocus(pos);
                cellRefs.current[i]?.focus();
                setDrag({ anchor: pos, over: pos });
              }}
              onPointerEnter={() => {
                setDrag((d) => (d ? { anchor: d.anchor, over: pos } : d));
              }}
              className={cn(
                'flex aspect-square min-w-0 flex-col items-center justify-center overflow-hidden rounded-cell text-2xs leading-tight outline-none',
                'focus-visible:ring-2 focus-visible:ring-foreground',
                isSelected && 'ring-2 ring-primary ring-inset',
                !isSelected && 'hover:ring-1 hover:ring-border',
              )}
              style={{ background: rangeLevelShade(cell?.level ?? 0) }}
            >
              <span className={cn('font-medium', empty ? 'text-subtle-foreground' : 'text-foreground')}>{cls}</span>
              {cell && cell.hands > 0 && (
                <span className={cn('tabular-nums', metric === 'won' ? moneyClass(cell.won_bb, 0) : 'text-muted-foreground')}>
                  {metric === 'won' ? formatSignedBb(cell.won_bb) : count(cell.hands)}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
