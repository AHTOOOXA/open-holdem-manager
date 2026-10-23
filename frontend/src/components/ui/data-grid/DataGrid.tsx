/**
 * DataGrid: the one dense grid behind Hands, Reports, Sessions, Marked Hands and the player
 * dialog. Hand2Note's grid behaviour in OHM's tokens, on TanStack Table v9 + TanStack Virtual.
 *
 * ```tsx
 * const col = createDataGridColumns<Row>();
 * const columns = col.columns([
 *   col.accessor('name', { header: 'Player', size: 160 }),
 *   col.accessor('won', { header: 'Won', meta: { numeric: true, tone: 'money' }, cell: (i) => usd(i.getValue()) }),
 * ]);
 * <DataGrid ariaLabel="Players" columns={columns} data={rows} getRowId={(r) => r.id} maxHeight={480} />
 * ```
 * Keep `columns` and `data` referentially stable (module scope / useMemo).
 *
 * Props
 * - columns            TanStack v9 column defs built with createDataGridColumns<T>(); `meta` below.
 * - data, getRowId     rows and their stable ids.
 * - summary            optional totals row, always pinned last (never sorted, hovered or selected);
 *   isSummaryRow       ...or flag a row inside `data` as the summary instead.
 *   stickySummary      keep it stuck to the bottom while the body scrolls.
 * - density            'default' (py-2, text-sm, ~36px rows) | 'compact' (py-1, text-cell, 26px).
 * - rowLines           1px subtle line under every row.
 * - sorting / onSortingChange / defaultSorting   controlled or uncontrolled single-column sort.
 *   manualSorting      the server sorts: rows are shown in `data` order.
 * - selection          'none' | 'single' (default) | 'multi' (checkbox column, Shift range, Cmd/Ctrl toggle).
 *   selectedRowIds / onSelectionChange   controlled selection (uncontrolled without selectedRowIds).
 * - onRowClick(row, e)  click on a body row. onRowActivate(row): Enter or double-click.
 * - persistKey         localStorage key suffix for column visibility and widths ("ohm.grid.<key>").
 * - columnPicker       gear menu in the header's last cell (default true). resizable (default true).
 * - virtualize         true | false | 'auto' (default: on above 200 rows). estimateRowHeight (px).
 * - onEndReached       infinite loading: called once per row count when one of the last
 *                      `endReachedThreshold` (10) rows renders.
 * - loading            skeleton rows when empty, a progress line under the header otherwise.
 * - error, empty       slots spanning all columns (empty defaults to "No results").
 * - stickyFirstColumn  first column stays put while scrolling sideways.
 * - ariaLabel          accessible name of the grid. className / maxHeight size the scroll box
 *                      (the box has contain-inline-size: give it a width, it never sizes to the table).
 * - handleRef          DataGridHandle.focusRow(id), e.g. to return focus to the row after a drawer closes.
 *
 * Column meta (DataGridColumnMeta): align, numeric (right-aligned, desc-first), title (tooltip +
 * picker label), tone: 'money' (+ moneyDigits), hideable, sortDescFirst, minWidth, className,
 * headerClassName. Width: TanStack `size` / `minSize` / `maxSize`; `enableSorting: false` to opt out.
 *
 * Keyboard (one tab stop in the body, roving tabindex on rows; header buttons are tab stops):
 * ArrowUp/ArrowDown move the active row, Home/End first/last, PageUp/PageDown by a page,
 * Enter activates, Space selects (toggles in multi; Shift+Space selects a range),
 * Cmd/Ctrl+A selects all (multi). Resize handles: ArrowLeft/ArrowRight (Shift: bigger steps),
 * Home = minimum width, Enter/double-click = default width.
 */
import {
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
  type Ref,
} from 'react';
import { useTable, type Cell, type Column, type Header, type Row, type RowData } from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ArrowDown, ArrowUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { moneyClass } from '@/lib/format';
import { Checkbox } from '@/components/ui/checkbox';
import { Skeleton } from '@/components/ui/skeleton';
import { ColumnPicker } from './ColumnPicker';
import { dataGridFeatures, type DataGridColumnDef, type DataGridColumnMeta, type DataGridFeatures } from './features';
import {
  ariaSortValue,
  clampWidth,
  computeSelection,
  endReachedIndex,
  hiddenFromVisibility,
  nextRowIndex,
  nextSorting,
  parseGridPrefs,
  pinSummaryLast,
  resizeByKey,
  revealScrollTop,
  rowsPerPage,
  selectAllState,
  serializeGridPrefs,
  shouldFireEndReached,
  shouldVirtualize,
  sortDirection,
  splitSummary,
  visibilityFromHidden,
  type ColumnPrefSpec,
  type GridSorting,
  type SelectionMode,
} from './logic';

/** Imperative handle (`handleRef`): move the active row to `id`, scroll it into view and focus it. */
export interface DataGridHandle {
  focusRow: (id: string) => void;
}

export interface DataGridProps<T extends RowData> {
  columns: DataGridColumnDef<T>[];
  data: readonly T[];
  getRowId: (row: T, index: number) => string;
  summary?: T | null;
  isSummaryRow?: (row: T) => boolean;
  stickySummary?: boolean;
  density?: 'default' | 'compact';
  rowLines?: boolean;
  sorting?: GridSorting;
  onSortingChange?: (sorting: GridSorting) => void;
  defaultSorting?: GridSorting;
  manualSorting?: boolean;
  selection?: SelectionMode;
  selectedRowIds?: readonly string[];
  onSelectionChange?: (ids: string[]) => void;
  onRowClick?: (row: T, event: React.MouseEvent<HTMLTableRowElement>) => void;
  onRowActivate?: (row: T) => void;
  persistKey?: string;
  columnPicker?: boolean;
  resizable?: boolean;
  virtualize?: boolean | 'auto';
  estimateRowHeight?: number;
  onEndReached?: () => void;
  endReachedThreshold?: number;
  loading?: boolean;
  error?: ReactNode;
  empty?: ReactNode;
  stickyFirstColumn?: boolean;
  ariaLabel: string;
  className?: string;
  maxHeight?: number | string;
  handleRef?: Ref<DataGridHandle>;
}

const SUMMARY_ROW_ID = '__ohm_summary__';
const HEADER_H = 28; // h-row-header
const SELECT_COL_W = 36;
const FILLER_MIN_W = 40;
const SKELETON_ROWS = 6;
const PREFS_PREFIX = 'ohm.grid.';
const EMPTY_IDS: readonly string[] = [];
const NO_SORTING: GridSorting = [];

const DEFAULT_COLUMN = { size: 120, minSize: 40, maxSize: 1000, sortUndefined: 'last' as const };

const RING_MID = 'group-focus-visible/row:shadow-[inset_0_2px_0_0_var(--color-ring),inset_0_-2px_0_0_var(--color-ring)]';
const RING_FIRST =
  'group-focus-visible/row:shadow-[inset_2px_0_0_0_var(--color-ring),inset_0_2px_0_0_var(--color-ring),inset_0_-2px_0_0_var(--color-ring)]';
const RING_LAST =
  'group-focus-visible/row:shadow-[inset_-2px_0_0_0_var(--color-ring),inset_0_2px_0_0_var(--color-ring),inset_0_-2px_0_0_var(--color-ring)]';

type GridColumn<T extends RowData> = Column<DataGridFeatures, T, unknown>;

function columnIdOf<T extends RowData>(def: DataGridColumnDef<T>): string {
  const d = def as { id?: string; accessorKey?: unknown; header?: unknown };
  if (d.id) return d.id;
  if (typeof d.accessorKey === 'string') return d.accessorKey.replace(/\./g, '_');
  if (typeof d.header === 'string') return d.header;
  return '';
}

function metaOf<T extends RowData>(column: GridColumn<T>): DataGridColumnMeta {
  return (column.columnDef.meta ?? {}) as DataGridColumnMeta;
}

function titleOf<T extends RowData>(column: GridColumn<T>): string {
  const meta = metaOf(column);
  if (meta.title) return meta.title;
  const header = column.columnDef.header;
  return typeof header === 'string' ? header : column.id;
}

function alignOf(meta: DataGridColumnMeta): 'left' | 'right' | 'center' {
  return meta.align ?? (meta.numeric ? 'right' : 'left');
}

const ALIGN_TEXT = { left: 'text-left', right: 'text-right', center: 'text-center' } as const;
const ALIGN_FLEX = { left: 'justify-start', right: 'justify-end', center: 'justify-center' } as const;

function readPrefs(key: string | undefined, spec: ColumnPrefSpec[]) {
  if (!key) return parseGridPrefs(null, spec);
  try {
    return parseGridPrefs(localStorage.getItem(PREFS_PREFIX + key), spec);
  } catch {
    return parseGridPrefs(null, spec);
  }
}

function sameIds(a: readonly string[], b: readonly string[]): boolean {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

export function DataGrid<T extends RowData>({
  columns,
  data,
  getRowId,
  summary,
  isSummaryRow,
  stickySummary = false,
  density = 'default',
  rowLines = false,
  sorting: sortingProp,
  onSortingChange,
  defaultSorting,
  manualSorting = false,
  selection = 'single',
  selectedRowIds,
  onSelectionChange,
  onRowClick,
  onRowActivate,
  persistKey,
  columnPicker = true,
  resizable = true,
  virtualize = 'auto',
  estimateRowHeight,
  onEndReached,
  endReachedThreshold = 10,
  loading = false,
  error,
  empty,
  stickyFirstColumn = false,
  ariaLabel,
  className,
  maxHeight,
  handleRef,
}: DataGridProps<T>) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const compact = density === 'compact';
  const rowH = estimateRowHeight ?? (compact ? 26 : 36);

  // ── Columns: first column locked visible, meta.minWidth -> minSize, meta.hideable -> enableHiding
  const prepared = useMemo(
    () =>
      columns.map((c, i) => {
        const meta = (c.meta ?? {}) as DataGridColumnMeta;
        const next = { ...c } as DataGridColumnDef<T> & { minSize?: number; enableHiding?: boolean; sortDescFirst?: boolean };
        if (next.minSize === undefined && meta.minWidth !== undefined) next.minSize = meta.minWidth;
        next.enableHiding = i === 0 ? false : (next.enableHiding ?? meta.hideable ?? true);
        if (next.sortDescFirst === undefined) next.sortDescFirst = meta.sortDescFirst ?? !!meta.numeric;
        return next;
      }),
    [columns],
  );

  const prefSpec = useMemo<ColumnPrefSpec[]>(
    () =>
      prepared.map((c) => {
        const d = c as { minSize?: number; maxSize?: number; enableHiding?: boolean };
        return {
          id: columnIdOf(c),
          hideable: d.enableHiding !== false,
          minSize: d.minSize ?? DEFAULT_COLUMN.minSize,
          maxSize: d.maxSize ?? DEFAULT_COLUMN.maxSize,
        };
      }),
    [prepared],
  );

  const [columnVisibility, setColumnVisibility] = useState<Record<string, boolean>>(() =>
    visibilityFromHidden(readPrefs(persistKey, prefSpec).hidden),
  );
  const [columnSizing, setColumnSizing] = useState<Record<string, number>>(() => readPrefs(persistKey, prefSpec).widths);

  useEffect(() => {
    if (!persistKey) return;
    try {
      localStorage.setItem(
        PREFS_PREFIX + persistKey,
        serializeGridPrefs({ hidden: hiddenFromVisibility(columnVisibility), widths: columnSizing }),
      );
    } catch {
      // localStorage unavailable
    }
  }, [persistKey, columnVisibility, columnSizing]);

  // ── Sorting (controlled or not)
  const [sortingInner, setSortingInner] = useState<GridSorting>(defaultSorting ?? NO_SORTING);
  const sorting = sortingProp ?? sortingInner;
  const setSorting = useCallback(
    (next: GridSorting) => {
      if (sortingProp === undefined) setSortingInner(next);
      onSortingChange?.(next);
    },
    [sortingProp, onSortingChange],
  );

  // ── Data + summary (the summary rides inside the table so its cells render like any other)
  const split = useMemo(() => splitSummary(data, summary, isSummaryRow), [data, summary, isSummaryRow]);
  const summaryData = split.summary;
  const tableData = useMemo(
    () => (summaryData ? [...split.rows, summaryData] : split.rows),
    [split.rows, summaryData],
  );
  const rowIdOf = useCallback(
    (row: T, index: number) => (row === summaryData ? SUMMARY_ROW_ID : getRowId(row, index)),
    [summaryData, getRowId],
  );

  const table = useTable({
    features: dataGridFeatures,
    columns: prepared,
    data: tableData,
    getRowId: rowIdOf,
    defaultColumn: DEFAULT_COLUMN,
    state: { sorting, columnVisibility, columnSizing },
    onSortingChange: (u) => setSorting(typeof u === 'function' ? u(sorting) : u),
    onColumnVisibilityChange: setColumnVisibility,
    onColumnSizingChange: setColumnSizing,
    manualSorting,
    enableSortingRemoval: false,
    enableMultiSort: false,
    columnResizeMode: 'onChange',
  });

  const pinned = pinSummaryLast(table.getRowModel().rows, summaryData ? SUMMARY_ROW_ID : null);
  const body = pinned.body;
  const summaryRow = pinned.summary;
  const bodyIds = body.map((r) => r.id);
  const visibleColumns = table.getVisibleLeafColumns();
  const headers = table.getHeaderGroups().at(-1)?.headers.filter((h) => h.column.getIsVisible()) ?? [];

  // ── Selection
  const selectable = selection !== 'none';
  const interactive = selectable || !!onRowClick || !!onRowActivate;
  const [selectedInner, setSelectedInner] = useState<readonly string[]>(EMPTY_IDS);
  const selected = selectedRowIds ?? selectedInner;
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const [anchor, setAnchor] = useState<string | null>(null);

  const commitSelection = (ids: string[]) => {
    if (selectedRowIds === undefined) setSelectedInner(ids);
    onSelectionChange?.(ids);
  };
  const select = (target: string, opts: { range?: boolean; toggle?: boolean } = {}) => {
    if (!selectable) return;
    const res = computeSelection({ mode: selection, current: selected, anchor, target, order: bodyIds, ...opts });
    setAnchor(res.anchor);
    if (!sameIds(res.ids, selected)) commitSelection(res.ids);
  };

  // ── Active row (keyboard focus); follows an outside change to a single selected row
  const [activeId, setActiveId] = useState<string | null>(null);
  const [seenSelection, setSeenSelection] = useState<readonly string[]>(selected);
  const [revealId, setRevealId] = useState<{ id: string } | null>(null);
  if (!sameIds(seenSelection, selected)) {
    setSeenSelection(selected);
    if (selected.length === 1 && selected[0] !== activeId) {
      setActiveId(selected[0]);
      setRevealId({ id: selected[0] });
    }
  }
  let activeIndex = activeId ? bodyIds.indexOf(activeId) : -1;
  if (activeIndex < 0 && selected.length > 0) activeIndex = bodyIds.indexOf(selected[0]);
  const tabStopIndex = activeIndex >= 0 ? activeIndex : 0;

  // ── Virtualisation
  const virtual = shouldVirtualize(virtualize, body.length);
  const summaryH = summaryRow && stickySummary ? rowH : 0;
  // Read fresh every render (no React Compiler in the build); the grid is not memoized.
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: virtual ? body.length : 0,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => rowH,
    overscan: 10,
    paddingStart: HEADER_H,
    scrollPaddingStart: HEADER_H,
    scrollPaddingEnd: summaryH,
    indexAttribute: 'data-row-index',
    getItemKey: (i) => bodyIds[i] ?? i,
  });
  const virtualItems = virtual ? virtualizer.getVirtualItems() : [];
  const padTop = virtual && virtualItems.length > 0 ? virtualItems[0].start - HEADER_H : 0;
  const padBottom =
    virtual && virtualItems.length > 0 ? virtualizer.getTotalSize() - virtualItems[virtualItems.length - 1].end : 0;
  const renderedIndexes: number[] = virtual ? virtualItems.map((v) => v.index) : body.map((_, i) => i);
  const tabStopRendered = renderedIndexes.includes(tabStopIndex);
  const fallbackTabStop = tabStopRendered ? tabStopIndex : (renderedIndexes[0] ?? -1);

  // ── Focus / reveal requests (set in handlers, applied after render)
  const focusReq = useRef<{ id: string; focus: boolean; scrolled?: boolean } | null>(null);
  useEffect(() => {
    if (revealId) focusReq.current = { id: revealId.id, focus: false };
  }, [revealId]);
  useEffect(() => {
    const req = focusReq.current;
    const root = scrollRef.current;
    if (!req || !root) return;
    const index = bodyIds.indexOf(req.id);
    if (index < 0) {
      focusReq.current = null;
      return;
    }
    const el = root.querySelector<HTMLTableRowElement>(`tr[data-row-index="${index}"]`);
    if (!el) {
      if (virtual && !req.scrolled) {
        req.scrolled = true;
        virtualizer.scrollToIndex(index, { align: 'auto' });
      } else focusReq.current = null;
      return;
    }
    const rootRect = root.getBoundingClientRect();
    const rect = el.getBoundingClientRect();
    if (root.scrollHeight <= root.clientHeight) {
      // The page scrolls, not the grid
      el.scrollIntoView({ block: 'nearest' });
      if (req.focus) el.focus({ preventScroll: true });
      focusReq.current = null;
      return;
    }
    const top = revealScrollTop({
      scrollTop: root.scrollTop,
      viewHeight: root.clientHeight,
      itemTop: rect.top - rootRect.top - root.clientTop + root.scrollTop,
      itemHeight: rect.height,
      headerHeight: HEADER_H,
      footerHeight: summaryH,
    });
    if (top !== null) root.scrollTop = top;
    if (req.focus) el.focus({ preventScroll: true });
    focusReq.current = null;
  });

  // Bumped to re-render (and so run the focus effect) when the active row id does not change
  const [, setFocusTick] = useState(0);
  useImperativeHandle(
    handleRef,
    () => ({
      focusRow: (id: string) => {
        setActiveId(id);
        focusReq.current = { id, focus: true };
        setFocusTick((t) => t + 1);
      },
    }),
    [],
  );

  const moveActive = (index: number) => {
    const id = bodyIds[index];
    if (id === undefined) return;
    setActiveId(id);
    focusReq.current = { id, focus: true };
    if (virtual) virtualizer.scrollToIndex(index, { align: 'auto' });
  };

  // ── Infinite loading
  const firedFor = useRef<number | null>(null);
  const lastVirtualIndex = virtualItems.length > 0 ? virtualItems[virtualItems.length - 1].index : -1;
  const endIndex = endReachedIndex(body.length, endReachedThreshold);
  useEffect(() => {
    if (!onEndReached || !virtual) return;
    if (
      shouldFireEndReached({
        lastRenderedIndex: lastVirtualIndex,
        count: body.length,
        threshold: endReachedThreshold,
        firedForCount: firedFor.current,
        loading,
      })
    ) {
      firedFor.current = body.length;
      onEndReached();
    }
  }, [onEndReached, virtual, lastVirtualIndex, body.length, endReachedThreshold, loading]);
  useEffect(() => {
    if (!onEndReached || virtual || loading || body.length === 0) return;
    const el = scrollRef.current?.querySelector(`tr[data-row-index="${endIndex}"]`);
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const count = body.length;
    const io = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      if (firedFor.current === count) return;
      firedFor.current = count;
      onEndReached();
    });
    io.observe(el);
    return () => io.disconnect();
  }, [onEndReached, virtual, loading, body.length, endIndex]);

  // ── Header shadow while scrolled
  const [scrolled, setScrolled] = useState(false);
  const onScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const s = e.currentTarget.scrollTop > 0;
    if (s !== scrolled) setScrolled(s);
  };

  // ── Keyboard
  const onBodyKeyDown = (e: React.KeyboardEvent<HTMLTableSectionElement>) => {
    const target = e.target as HTMLElement;
    const attr = target.dataset.rowIndex;
    if (attr === undefined || target.tagName !== 'TR') return; // keys inside cell controls stay theirs
    const index = Number(attr);
    const row = body[index];
    if (!row) return;
    const root = scrollRef.current;
    const page = rowsPerPage(root?.clientHeight ?? 0, HEADER_H + summaryH, target.offsetHeight || rowH);
    const next = nextRowIndex(e.key, index, body.length, page);
    if (next !== null && !e.altKey && !e.metaKey && !e.ctrlKey) {
      e.preventDefault();
      if (e.shiftKey && selection === 'multi' && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
        select(bodyIds[next], { range: true });
      }
      moveActive(next);
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      onRowActivate?.(row.original);
    } else if (e.key === ' ') {
      e.preventDefault();
      select(row.id, { toggle: selection === 'multi', range: e.shiftKey });
    } else if ((e.key === 'a' || e.key === 'A') && (e.metaKey || e.ctrlKey) && selection === 'multi') {
      e.preventDefault();
      commitSelection([...bodyIds]);
    }
  };

  // ── Layout
  const multi = selection === 'multi';
  const leadW = multi ? SELECT_COL_W : 0;
  const totalW = leadW + table.getTotalSize() + FILLER_MIN_W;
  const colCount = visibleColumns.length + (multi ? 1 : 0) + 1;
  const padY = compact ? 'py-1' : 'py-2';
  const textSize = compact ? 'text-cell' : 'text-sm';
  const firstColId = visibleColumns[0]?.id;
  const stickyLeft = leadW;

  const resetColumns = () => {
    setColumnVisibility({});
    setColumnSizing({});
  };

  const pickerItems = table.getAllLeafColumns().map((c) => ({
    id: c.id,
    label: titleOf(c),
    visible: c.getIsVisible(),
    canHide: c.getCanHide(),
  }));

  const renderHeader = (header: Header<DataGridFeatures, T, unknown>, i: number) => {
    const column = header.column;
    const meta = metaOf(column);
    const align = alignOf(meta);
    const title = titleOf(column);
    const canSort = column.getCanSort();
    const dir = sortDirection(sorting, column.id);
    const isFirst = i === 0 && !multi;
    const sticky = stickyFirstColumn && column.id === firstColId;
    const def = column.columnDef.header;
    const label =
      typeof def === 'string' || def === undefined ? (
        <span className="truncate">{def ?? column.id}</span>
      ) : (
        <span className="min-w-0 truncate">
          <table.FlexRender header={header} />
        </span>
      );
    const arrow = dir ? (
      dir === 'desc' ? (
        <ArrowDown className="size-3 shrink-0" aria-hidden />
      ) : (
        <ArrowUp className="size-3 shrink-0" aria-hidden />
      )
    ) : null;
    return (
      <th
        key={header.id}
        scope="col"
        aria-sort={canSort ? ariaSortValue(dir) : undefined}
       
        style={sticky ? { left: stickyLeft } : undefined}
        className={cn(
          headerCellBase,
          sticky ? 'left-0 z-[calc(var(--z-sticky)+2)] border-r border-r-border-subtle' : 'z-[calc(var(--z-sticky)+1)]',
          meta.headerClassName,
        )}
      >
        <div className={cn('flex h-full min-w-0 items-center px-2', isFirst && 'pl-6', ALIGN_FLEX[align])}>
          {canSort ? (
            <button
              type="button"
              title={title}
              onClick={() => setSorting(nextSorting(sorting, column.id, column.columnDef.sortDescFirst ?? false))}
              className={cn(
                'inline-flex min-w-0 max-w-full items-center gap-1 rounded-cell outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring',
                dir && 'text-foreground',
                align === 'right' && 'flex-row-reverse',
              )}
            >
              {label}
              {arrow}
            </button>
          ) : (
            <span className="inline-flex min-w-0 max-w-full" title={title}>
              {label}
            </span>
          )}
        </div>
        {resizable && column.getCanResize() && (
          <ResizeHandle header={header} title={typeof def === 'string' ? def : title} onSize={(w) => setColumnSizing((s) => ({ ...s, [column.id]: w }))} />
        )}
      </th>
    );
  };

  const cellClass = (
    column: GridColumn<T>,
    cell: Cell<DataGridFeatures, T, unknown> | null,
    isFirst: boolean,
    sticky: boolean,
  ) => {
    const meta = metaOf(column);
    const value = cell?.getValue();
    return cn(
      padY,
      'overflow-hidden px-2 text-ellipsis whitespace-nowrap',
      isFirst && 'pl-6',
      ALIGN_TEXT[alignOf(meta)],
      meta.tone === 'money' && typeof value === 'number' && moneyClass(value, meta.moneyDigits ?? 2),
      sticky && 'sticky z-(--z-sticky) border-r border-border-subtle bg-card',
      meta.className,
    );
  };

  const renderRow = (row: Row<DataGridFeatures, T>, index: number) => {
    const isSelected = selectable && selectedSet.has(row.id);
    const cells = row.getVisibleCells();
    const stateBg = isSelected ? 'bg-selection' : '';
    const stickyState = isSelected
      ? 'bg-linear-to-r from-selection to-selection'
      : interactive
        ? 'group-hover/row:bg-linear-to-r group-hover/row:from-overlay-hover group-hover/row:to-overlay-hover'
        : '';
    const line = rowLines && 'border-b border-border-subtle';
    return (
      <tr
        key={row.id}
        data-row-index={index}
        data-row-id={row.id}
        data-selected={isSelected || undefined}
        ref={virtual ? virtualizer.measureElement : undefined}
        tabIndex={index === fallbackTabStop ? 0 : -1}
        aria-rowindex={index + 2}
        aria-selected={selectable ? isSelected : undefined}
        onFocus={(e) => {
          if (e.target === e.currentTarget && activeId !== row.id) setActiveId(row.id);
        }}
        onMouseDown={(e) => {
          if (e.shiftKey && multi) e.preventDefault(); // no text selection on range clicks
        }}
        onClick={(e) => {
          setActiveId(row.id);
          select(row.id, { range: e.shiftKey, toggle: e.metaKey || e.ctrlKey });
          onRowClick?.(row.original, e);
        }}
        onDoubleClick={() => onRowActivate?.(row.original)}
        className={cn(
          'group/row outline-none',
          interactive && 'cursor-pointer',
          interactive && !isSelected && 'hover:bg-overlay-hover',
        )}
      >
        {multi && (
          <td
            className={cn(
              padY,
              'pr-0 pl-3',
              stickyFirstColumn ? cn('sticky left-0 z-(--z-sticky) bg-card', stickyState) : stateBg,
              line,
              CELL_TRANSITION,
              RING_FIRST,
            )}
          >
            <Checkbox
              checked={isSelected}
              tabIndex={-1}
              aria-label="Select row"
              onClick={(e) => e.stopPropagation()}
              onCheckedChange={() => select(row.id, { toggle: true })}
            />
          </td>
        )}
        {cells.map((cell, ci) => {
          const sticky = stickyFirstColumn && cell.column.id === firstColId;
          return (
            <td
              key={cell.id}
              style={sticky ? { left: stickyLeft } : undefined}
              className={cn(
                cellClass(cell.column, cell, ci === 0 && !multi, sticky),
                sticky ? stickyState : stateBg,
                line,
                CELL_TRANSITION,
                ci === 0 && !multi ? RING_FIRST : RING_MID,
              )}
            >
              <table.FlexRender cell={cell} />
            </td>
          );
        })}
        <td aria-hidden className={cn(stateBg, line, CELL_TRANSITION, RING_LAST)} />
      </tr>
    );
  };

  const selectAll = multi ? selectAllState(selected, bodyIds) : false;
  const showSkeleton = loading && body.length === 0 && !error;
  const showProgress = loading && body.length > 0;

  return (
    // contain-inline-size: a wide table scrolls inside the box instead of widening every ancestor
    <div
      ref={scrollRef}
      onScroll={onScroll}
      style={maxHeight !== undefined ? { maxHeight } : undefined}
      className={cn('relative contain-inline-size overflow-auto rounded-card border border-border bg-card', className)}
    >
      {/* One fade under the sticky header while the body is scrolled (zero layout height) */}
      <div
        aria-hidden
        className={cn(
          'pointer-events-none sticky top-row-header left-0 z-[calc(var(--z-sticky)+3)] -mb-2 h-2 w-full bg-linear-to-b from-background to-transparent transition-opacity duration-(--motion-fast)',
          scrolled ? 'opacity-100' : 'opacity-0',
        )}
      />
      {showProgress && (
        <div
          aria-hidden
          className="pointer-events-none sticky top-[26px] left-0 z-[calc(var(--z-sticky)+3)] -mb-0.5 h-0.5 w-full animate-pulse bg-primary"
        />
      )}
      <table
        role="grid"
        aria-label={ariaLabel}
        aria-rowcount={body.length + 1 + (summaryRow ? 1 : 0)}
        aria-multiselectable={multi || undefined}
        aria-busy={loading || undefined}
        className={cn('w-full table-fixed border-separate border-spacing-0', textSize)}
        style={{ minWidth: totalW }}
      >
        <colgroup>
          {multi && <col style={{ width: SELECT_COL_W }} />}
          {visibleColumns.map((c) => (
            <col key={c.id} style={{ width: c.getSize() }} />
          ))}
          <col />
        </colgroup>
        <thead>
          <tr aria-rowindex={1}>
            {multi && (
              <th
                scope="col"
               
                className={cn(
                  headerCellBase,
                  stickyFirstColumn ? 'left-0 z-[calc(var(--z-sticky)+2)]' : 'z-[calc(var(--z-sticky)+1)]',
                  'pr-0 pl-3',
                )}
              >
                <Checkbox
                  checked={selectAll}
                  aria-label="Select all rows"
                  disabled={bodyIds.length === 0}
                  onCheckedChange={() => commitSelection(selectAll === true ? [] : [...bodyIds])}
                />
              </th>
            )}
            {headers.map(renderHeader)}
            <th className={cn(headerCellBase, 'z-[calc(var(--z-sticky)+1)] pr-1 text-right')}>
              {columnPicker && (
                <ColumnPicker
                  items={pickerItems}
                  onToggle={(id, v) => setColumnVisibility((s) => ({ ...s, [id]: v }))}
                  onReset={resetColumns}
                />
              )}
            </th>
          </tr>
        </thead>
        <tbody onKeyDown={onBodyKeyDown}>
          {error ? (
            <tr>
              <td colSpan={colCount} className="px-6 py-8 text-center text-sm text-money-neg">
                {error}
              </td>
            </tr>
          ) : showSkeleton ? (
            Array.from({ length: SKELETON_ROWS }, (_, r) => (
              <tr key={r} aria-hidden>
                {multi && <td className={padY} />}
                {visibleColumns.map((c, ci) => (
                  <td key={c.id} className={cn(padY, 'px-2', ci === 0 && !multi && 'pl-6')}>
                    <Skeleton className={cn('h-3 rounded-cell', alignOf(metaOf(c)) === 'right' ? 'ml-auto w-1/2' : 'w-3/4')} />
                  </td>
                ))}
                <td />
              </tr>
            ))
          ) : body.length === 0 ? (
            <tr>
              <td colSpan={colCount} className="px-6 py-8 text-center text-sm text-muted-foreground">
                {empty ?? 'No results'}
              </td>
            </tr>
          ) : (
            <>
              {padTop > 0 && (
                <tr aria-hidden style={{ height: padTop }}>
                  <td colSpan={colCount} className="p-0" />
                </tr>
              )}
              {renderedIndexes.map((i) => renderRow(body[i], i))}
              {padBottom > 0 && (
                <tr aria-hidden style={{ height: padBottom }}>
                  <td colSpan={colCount} className="p-0" />
                </tr>
              )}
            </>
          )}
        </tbody>
        {summaryRow && !error && (
          <tfoot>
            <tr data-summary aria-rowindex={body.length + 2} className="font-medium">
              {multi && (
                <td
                  className={cn(
                    padY,
                    summaryCellBase,
                    stickySummary && summaryStickyClass,
                    stickyFirstColumn && 'sticky left-0 z-[calc(var(--z-sticky)+2)]',
                  )}
                />
              )}
              {summaryRow.getVisibleCells().map((cell, ci) => {
                const sticky = stickyFirstColumn && cell.column.id === firstColId;
                const style: CSSProperties | undefined = sticky ? { left: stickyLeft } : undefined;
                return (
                  <td
                    key={cell.id}
                    style={style}
                    className={cn(
                      cellClass(cell.column, cell, ci === 0 && !multi, sticky),
                      summaryCellBase,
                      stickySummary && summaryStickyClass,
                      sticky && stickySummary && 'z-[calc(var(--z-sticky)+2)]',
                    )}
                  >
                    <table.FlexRender cell={cell} />
                  </td>
                );
              })}
              <td aria-hidden className={cn(summaryCellBase, stickySummary && summaryStickyClass)} />
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

const headerCellBase =
  "sticky top-0 h-row-header border-b border-border bg-card p-0 text-left align-middle text-xs font-medium whitespace-nowrap text-muted-foreground";
const summaryCellBase = 'border-t border-border bg-card';
const summaryStickyClass = 'sticky bottom-0 z-[calc(var(--z-sticky)+1)]';
const CELL_TRANSITION = 'transition-[background-color] duration-(--motion-fast)';

function ResizeHandle<T extends RowData>({
  header,
  title,
  onSize,
}: {
  header: Header<DataGridFeatures, T, unknown>;
  title: string;
  onSize: (width: number) => void;
}) {
  const column = header.column;
  const def = column.columnDef as { minSize?: number; maxSize?: number };
  const min = def.minSize ?? DEFAULT_COLUMN.minSize;
  const max = def.maxSize ?? DEFAULT_COLUMN.maxSize;
  const size = header.getSize();
  const handler = header.getResizeHandler();
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={`Resize ${title} column`}
      aria-valuenow={Math.round(size)}
      aria-valuemin={min}
      aria-valuemax={max}
      tabIndex={0}
      data-resizing={column.getIsResizing() || undefined}
      onMouseDown={handler}
      onTouchStart={handler}
      onClick={(e) => e.stopPropagation()}
      onDoubleClick={() => column.resetSize()}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          column.resetSize();
          return;
        }
        const next = resizeByKey(e.key, size, { min, max }, e.shiftKey);
        if (next === null) return;
        e.preventDefault();
        onSize(clampWidth(next, min, max));
      }}
      className="absolute top-0 right-0 z-1 h-full w-1.5 cursor-ew-resize touch-none outline-none select-none after:absolute after:inset-y-1.5 after:right-0 after:w-px after:bg-border hover:after:w-0.5 hover:after:bg-primary focus-visible:after:w-0.5 focus-visible:after:bg-ring data-[resizing]:after:w-0.5 data-[resizing]:after:bg-primary"
    />
  );
}
