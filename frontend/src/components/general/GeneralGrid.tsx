import { useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { GENERAL_CELLS, GENERAL_LAYOUT } from '@/lib/h2n-layout';
import type { LayoutCell, LayoutTable } from '@/lib/h2n-layout';
import type { H2NCellInput } from '@/lib/h2n-format';
import { H2NEmptyCell, H2NStatCell, H2NTextCell } from './H2NCell';

interface GeneralGridProps {
  cells: Record<string, H2NCellInput>;
  playerName: string;
  selectedCellId: string | null;
  onSelectCell: (id: string) => void;
  layout?: readonly LayoutTable[];
}

/** Cells whose centres are this close vertically are treated as one row. */
const ROW_TOLERANCE_PX = 6;

const NAV_KEYS = new Set(['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End']);

/**
 * Next cell for an arrow key, found from the rendered geometry so it works
 * across the separate tables: Left/Right stay in the visual row, Up/Down jump
 * to the nearest row above/below and pick the horizontally closest cell.
 */
function neighbour(cells: HTMLElement[], from: HTMLElement, key: string): HTMLElement | null {
  const centre = (el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  };
  const c = centre(from);
  const others = cells.filter((el) => el !== from).map((el) => ({ el, ...centre(el) }));
  const sameRow = others.filter((o) => Math.abs(o.y - c.y) <= ROW_TOLERANCE_PX);
  const nearestX = (list: typeof others) =>
    list.reduce<(typeof others)[number] | null>((best, o) => (!best || Math.abs(o.x - c.x) < Math.abs(best.x - c.x) ? o : best), null)?.el ?? null;

  switch (key) {
    case 'ArrowRight':
      return nearestX(sameRow.filter((o) => o.x > c.x));
    case 'ArrowLeft':
      return nearestX(sameRow.filter((o) => o.x < c.x));
    case 'Home':
      return sameRow.filter((o) => o.x < c.x).sort((a, b) => a.x - b.x)[0]?.el ?? null;
    case 'End':
      return sameRow.filter((o) => o.x > c.x).sort((a, b) => b.x - a.x)[0]?.el ?? null;
    case 'ArrowDown':
    case 'ArrowUp': {
      const down = key === 'ArrowDown';
      const candidates = others.filter((o) => (down ? o.y - c.y : c.y - o.y) > ROW_TOLERANCE_PX);
      if (candidates.length === 0) return null;
      const rowY = down ? Math.min(...candidates.map((o) => o.y)) : Math.max(...candidates.map((o) => o.y));
      return nearestX(candidates.filter((o) => Math.abs(o.y - rowY) <= ROW_TOLERANCE_PX));
    }
    default:
      return null;
  }
}

/**
 * The General page: a single column of tables, 8px apart. Each table is a CSS
 * grid whose tracks size to their content; every grid position renders a
 * cell (empty ones too), so spacer rows and columns come out 8px from the
 * cell padding alone.
 */
export default function GeneralGrid({
  cells,
  playerName,
  selectedCellId,
  onSelectCell,
  layout = GENERAL_LAYOUT,
}: GeneralGridProps) {
  // Roving tabindex: the grid is a single tab stop; arrow keys move between stat cells.
  const statIds = useMemo(
    () => layout.flatMap((t) => t.rows.flatMap((row) => row.flatMap((c) => (c.type === 'stat' && GENERAL_CELLS[c.id] ? [c.id] : [])))),
    [layout],
  );
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const activeId =
    (focusedId && statIds.includes(focusedId) && focusedId) ||
    (selectedCellId && statIds.includes(selectedCellId) && selectedCellId) ||
    statIds[0] ||
    null;
  const rootRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!NAV_KEYS.has(e.key)) return;
    const from = (e.target as HTMLElement).closest<HTMLElement>('[data-cell-id]');
    if (!from || !rootRef.current) return;
    const all = Array.from(rootRef.current.querySelectorAll<HTMLElement>('[data-cell-id]'));
    let next: HTMLElement | null;
    if (e.key === 'Home' && e.ctrlKey) next = all[0] ?? null;
    else if (e.key === 'End' && e.ctrlKey) next = all[all.length - 1] ?? null;
    else next = neighbour(all, from, e.key);
    e.preventDefault();
    if (next && next !== from) next.focus();
  };

  const renderCell = (cell: LayoutCell, key: string) => {
    switch (cell.type) {
      case 'empty':
        return <H2NEmptyCell key={key} span={cell.span} />;
      case 'text':
        return (
          <H2NTextCell
            key={key}
            text={cell.text}
            tone={cell.tone}
            section={cell.section}
            align={cell.align}
            span={cell.span}
          />
        );
      case 'nickname':
        return <H2NTextCell key={key} text={playerName} tone={cell.tone} />;
      case 'stat': {
        const meta = GENERAL_CELLS[cell.id];
        if (!meta) return <H2NEmptyCell key={key} span={cell.span} />;
        return (
          <H2NStatCell
            key={key}
            meta={meta}
            data={cells[cell.id]}
            tone={cell.tone}
            align={cell.align}
            span={cell.span}
            selected={selectedCellId === cell.id}
            onSelect={onSelectCell}
            tabIndex={cell.id === activeId ? 0 : -1}
            onFocus={setFocusedId}
          />
        );
      }
    }
  };

  return (
    <div
      ref={rootRef}
      role="group"
      aria-label="Statistics. Use the arrow keys to move between cells, Enter to open one."
      onKeyDown={handleKeyDown}
      // 14px text on an 18px line + 4px cell padding = a 26px row (h-row-dense); tables 8px apart, 16px inset.
      className="grid content-start items-start justify-start gap-2 px-4 text-sm leading-4.5 font-normal text-foreground"
    >
      {layout.map((table) => (
        <div
          key={table.id}
          data-table={table.id}
          className="grid"
          style={{
            gridTemplateColumns: table.tracks ? table.tracks.join(' ') : `repeat(${table.columns}, auto)`,
            gridAutoRows: 'auto',
            justifyContent: 'start',
            marginBottom: table.marginBottom,
          }}
        >
          {table.rows.flatMap((row, r) => row.map((cell, c) => renderCell(cell, `${r}-${c}`)))}
        </div>
      ))}
    </div>
  );
}
