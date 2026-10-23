/**
 * One split-report lower tab: POST /api/reports/split rendered with DataGrid. Columns come from the
 * response; the summary row is pinned last; a row click selects it and opens the next page.
 */
import { useCallback, useMemo } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { DataGrid, createDataGridColumns, statCell, type DataGridColumnDef } from '@/components/ui/data-grid';
import { getSplit } from '@/lib/reports/api';
import { reportKeys } from '@/lib/reports/query-keys';
import { formatReportValue, NO_VALUE } from '@/lib/reports/format-value';
import { LOWER_TAB_CAPTION } from '@/lib/reports/catalog';
import type { ReportQuery, SplitColumn, SplitResponse, SplitRow, SplitType } from '@/lib/reports/types';

interface GridRow {
  key: string;
  caption: string;
  values: Record<string, number | null>;
  src: SplitRow | null;
}

const SUMMARY_KEY = '__summary__';
const GRID_MAX_HEIGHT = 'max(18rem, calc(100dvh - 20rem))';
const col = createDataGridColumns<GridRow>();
const rowId = (r: GridRow) => r.key;

function valueCell(c: SplitColumn) {
  if (c.format === 'pct' && c.sample) {
    const sampleId = c.sample;
    return statCell<GridRow>((r) => r.values[sampleId] ?? null, 'pct');
  }
  return function ValueCell({ row }: { row: { original: GridRow } }) {
    const v = row.original.values[c.id];
    const text = formatReportValue(v, c.format);
    return text === NO_VALUE ? <span className="text-subtle-foreground">{NO_VALUE}</span> : text;
  };
}

function buildColumns(entryHeader: string, columns: SplitColumn[]): DataGridColumnDef<GridRow>[] {
  return col.columns([
    col.accessor('caption', {
      id: 'entry',
      header: entryHeader,
      size: 200,
      meta: { hideable: false },
    }),
    ...columns.map((c) =>
      col.accessor((r) => r.values[c.id] ?? null, {
        id: c.id,
        header: c.abbrev ?? c.caption,
        size: 96,
        meta: { numeric: true, title: c.caption, tone: c.winnings ? 'money' : undefined },
        cell: valueCell(c),
      }),
    ),
  ]);
}

export default function SplitReport({ type, query, selectedKey, onOpenRow }: {
  type: SplitType;
  /** Full chain of the page (inherited + own + range selections). */
  query: ReportQuery;
  selectedKey: string | null;
  onOpenRow: (row: SplitRow) => void;
}) {
  const q = useQuery<SplitResponse>({
    queryKey: reportKeys.split(type, query),
    queryFn: ({ signal }) => getSplit({ ...query, type }, signal),
    placeholderData: keepPreviousData,
  });
  const data = q.data?.type === type ? q.data : undefined;

  const entryHeader = data?.entry_header ?? LOWER_TAB_CAPTION[type];
  const responseColumns = data?.columns;
  const columns = useMemo(() => buildColumns(entryHeader, responseColumns ?? []), [entryHeader, responseColumns]);
  const responseRows = data?.rows;
  const rows = useMemo<GridRow[]>(
    () => (responseRows ?? []).map((r) => ({ key: r.key, caption: r.caption, values: r.values, src: r })),
    [responseRows],
  );
  const responseSummary = data?.summary;
  const summary = useMemo<GridRow | null>(
    () => (responseSummary && rows.length > 1
      ? { key: SUMMARY_KEY, caption: 'Summary', values: responseSummary, src: null }
      : null),
    [responseSummary, rows.length],
  );
  const selectedIds = useMemo(() => (selectedKey ? [selectedKey] : []), [selectedKey]);

  const open = useCallback((r: GridRow) => { if (r.src) onOpenRow(r.src); }, [onOpenRow]);
  const onSelectionChange = useCallback((ids: string[]) => {
    const r = rows.find((x) => x.key === ids[0]);
    if (r) open(r);
  }, [rows, open]);

  return (
    <DataGrid
      ariaLabel={LOWER_TAB_CAPTION[type]}
      columns={columns}
      data={rows}
      getRowId={rowId}
      summary={summary}
      stickySummary
      density="default"
      selection="single"
      selectedRowIds={selectedIds}
      onSelectionChange={onSelectionChange}
      onRowActivate={open}
      persistKey={`report.${type}`}
      loading={q.isFetching}
      error={q.isError ? <span className="text-sm text-muted-foreground">Couldn't load this report. {q.error.message}</span> : undefined}
      empty="No results yet"
      maxHeight={GRID_MAX_HEIGHT}
      stickyFirstColumn
      className="w-full"
    />
  );
}
